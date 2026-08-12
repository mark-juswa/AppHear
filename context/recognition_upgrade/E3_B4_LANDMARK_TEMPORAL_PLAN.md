# E3-B4 Landmark Temporal Plan

**Purpose:** Compare landmark-only temporal model heads after E3-B3 showed that the structured
landmark branch substantially outperformed RGB-only and landmark+RGB fusion on the bounded 7-class
signer-disjoint split.

**Scope:** Experiment planning and user-run handoff only. This does not authorize Android
integration, production model replacement, dataset changes, or changes to the current `[96,258]`
recognizer.

**Current status:** Completed. See `E3_B4_RESULT.md`; masked TCN passed directionally and larger validation is next.

**Last updated:** 2026-07-28.

## Verified Project References

- E3-B3 run directory:
  `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion`
- E3-B3 landmark tensor:
  `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion/dataset/landmark_features.npz`
- Tensor contract: `landmarks` shape `[168,96,258]`, `y` shape `[168]`, `split_index` shape
  `[168]`, `frame_mask` shape `[168,96]`.
- Split: 112 train, 28 validation, 28 test.
- Classes: `DOG1`, `BITE1`, `DEMAND1`, `WHATFOR1`, `DEAF1`, `PARTY1`, `ROCKINGCHAIR1`.
- Source model builder: `model/model.py`, especially `build_encoder()` and `build_classifier()`.
- E3-B3 landmark-only reference: best validation/test `0.6071/0.6071`; latest test `0.6786`.
- E3-B3 RGB-only reference: best validation/test `0.2500/0.2500`.
- E3-B3 fusion reference: best validation/test `0.2857/0.2500`.

## Source Of Truth Files

- Runner: `pipeline/rgb/e3_b4_landmark_temporal.py`
- Package output:
  `artifacts/recognition_upgrade/e3_landmark_temporal/pilot_01_tcn_vs_masked`
- Related context: `E3_B3_RESULT.md`, `EXPERIMENT_MATRIX.md`, `MODEL_RESEARCH_PLAN.md`,
  `TEMPORAL_AND_BOUNDARY_PLAN.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`.

## Architecture Decision

E3-B4 keeps landmarks only and tests whether AppHear's temporal encoder path is better than the
simple E3-B3 landmark Conv1D head.

Branches:

- `conv1d_baseline`: the same class of simple landmark temporal head used in E3-B3.
- `tcn_pool`: AppHear causal TCN encoder from `model/model.py` with ordinary global average pooling.
- `tcn_masked_pool`: same causal TCN encoder, but padded frames are excluded using `frame_mask`.

This is intentionally not a GCN/ST-GCN test. The earlier E1 GCN path proved capacity on a sanity
slice but remains expensive and unresolved for full matched training. E3-B4 is the cheaper next
question: whether the already-supported TCN temporal structure improves the strongest current
branch before spending effort on heavier graph or RGB work.

## Assumptions

- The E3-B3 tensor and manifest are valid and remain the controlled split for this test.
- The validation set is used for model selection; test is used only to compare the selected result.
- Because the split has only 28 validation and 28 test clips, results are directional, not release
  evidence.

## Risks

- Small validation/test sets can swing by one or two clips.
- The TCN may overfit or underperform the simpler Conv1D head on only 112 training clips.
- Masked pooling can improve padding handling but may not help if most clips already use most of
  the 96-frame window.
- Repeated iteration on this same test split can bias future decisions.

## Open Questions

- Does causal TCN beat the simple landmark Conv1D control on validation while preserving test
  accuracy?
- Does explicit padded-frame masking improve or hurt the TCN branch?
- If TCN does not improve the 7-class pilot, should the next scale test use the simple landmark
  head, the existing production TCN, or a larger dataset before revisiting architecture?

## Gate

Promising:

- Best validation accuracy is at least the E3-B3 landmark-only best validation accuracy `0.6071`.
- The selected checkpoint's test accuracy is not worse than E3-B3 landmark-only best test `0.6071`.
- `tcn_masked_pool` is not worse than `tcn_pool` on validation.

No-go:

- TCN variants fail to match the simple Conv1D control.
- Training accuracy rises while validation/test collapse.
- Predictions collapse to one or two classes.

## Next Required Action

User runs:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b4_landmark_temporal run --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_landmark_temporal\pilot_01_tcn_vs_masked"
```

Then verify:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b4_landmark_temporal check --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_landmark_temporal\pilot_01_tcn_vs_masked"
```

## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement
  is authorized.
- **Verified project references:** Paths and metrics listed above.
- **Related context files:** `README.md`, `EXPERIMENT_MATRIX.md`, `E3_B3_RESULT.md`.
- **Architecture decisions:** E3-B4 follows the landmark-first decision after E3-B3 fusion no-go.
- **Assumptions:** The E3-B3 split remains the controlled pilot split.
- **Open questions:** Listed above.
- **Risks:** Listed above and tracked in `RISK_REGISTER.md`.
- **Next required action:** Prepare larger multi-seed landmark-temporal validation.

