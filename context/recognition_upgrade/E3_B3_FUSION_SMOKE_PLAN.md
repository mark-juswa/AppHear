# E3-B3 Landmark + RGB Fusion Smoke Plan

**Purpose:** Test whether RGB adds complementary signal when fused with landmarks after standalone
RGB failed E3-B0, E3-B1, and E3-B2 gates.

**Scope:** Bounded signer-disjoint experiment only. This does not authorize Android integration,
production model replacement, full E3 training, detector training, or feature-schema changes.

**Current status:** PACKAGE PREPARED / USER RUN PENDING.

**Last updated:** 2026-07-28.

## Verified Project References

- Runner: `pipeline/rgb/e3_b3_fusion_smoke.py`.
- Package: `artifacts/recognition_upgrade/e3_fusion/pilot_01_landmark_rgb_fusion`.
- Source RGB run: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body`.
- RGB features: `artifacts/recognition_upgrade/e3_rgb_b1/pilot_01_mobilenetv3_upper_body/dataset/rgb_frame_features.npz`.
- Landmark root: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/landmarks`.
- Span root: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/spans`.
- Normalization config: `pipeline/config/normalize.yaml`.
- Previous RGB result: `context/recognition_upgrade/E3_B2_RESULT.md`.

## Prepared Package

- Classes: 7 (`DOG1`, `BITE1`, `DEMAND1`, `WHATFOR1`, `DEAF1`, `PARTY1`,
  `ROCKINGCHAIR1`).
- Clips: 168.
- Split: 112 train, 28 validation, 28 test.
- Per-class support: 16 train, 4 validation, 4 test.
- Split policy: signer-disjoint, inherited from E3-B0/E3-B1.
- Landmark input: `[96, 258]` v3.0 streaming features rebuilt from existing Stage-E landmarks and
  spans.
- RGB input: `[16, 576]` MobileNetV3 frame embeddings from E3-B1.
- Branches trained on same split: `rgb_only`, `landmark_only`, `fusion`.
- Epochs per command: 8.

## Why This Is Cheap Enough

This package does not rerun MediaPipe or RGB embedding extraction. Landmark features are rebuilt
from already-existing `.npz` landmark files and `.span.json` sidecars for the same manifest rows.
RGB embeddings are reused from E3-B1.

## Evaluation Gate

The goal is not high final accuracy. The goal is to see whether fusion beats both branch-only heads
on the same held-out signer split.

Interpretation:

- **Promising:** fusion best checkpoint beats both `landmark_only` and `rgb_only` on validation and
  does not regress test.
- **No-go:** fusion is equal/worse than landmark-only or follows RGB-only collapse.
- **Stop condition:** if landmark-only is already weak on this 7-class split, return to landmark
  temporal/feature improvements before any more RGB work.

## User Commands

Run:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b3_fusion_smoke run `
  --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_fusion\pilot_01_landmark_rgb_fusion"
```

Check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b3_fusion_smoke check `
  --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_fusion\pilot_01_landmark_rgb_fusion"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e3_b3_fusion_smoke run `
  --run-dir "F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e3_fusion\pilot_01_landmark_rgb_fusion" `
  --resume
```

## Assumptions

- E3-B1 RGB embeddings remain aligned with the inherited pilot manifest order.
- Existing Stage-E landmark and span files are valid for all 168 clips.
- Small heads are sufficient for a smoke comparison, not final architecture selection.

## Risks

- The fusion result may be noisy because the split has only 28 validation and 28 test clips.
- A naive concatenation head can underuse one branch.
- If landmark-only is weak on this subset, fusion cannot answer the larger architecture question.

## Next Required Action

User runs E3-B3 and sends back the completed run output. Stop after check; do not start full E3
training or Android integration.

