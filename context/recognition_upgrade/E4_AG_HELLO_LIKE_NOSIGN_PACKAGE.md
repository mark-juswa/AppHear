# E4-AG HELLO-Like No-Sign Expansion Package

**Purpose:** Add targeted no-sign examples that resemble the remaining `NO_SIGN -> HELLO` false commits, then retrain/evaluate the signing gate without changing the production Android recognizer.

**Scope:** Offline capture, review, feature extraction, dataset expansion, and gate evaluation only. No Android integration, TFLite export, production recognizer replacement, source dataset mutation, or vocabulary expansion.

**Current status:** PREPARED / USER CAPTURE NEXT.

**Last updated:** 2026-08-02.

## Why This Exists

E4-AF proved that policy-only tuning is not enough. The system can remove `HELLO` false commits by making HELLO stricter, but that damages true HELLO recall and positive coverage. Therefore the correct next step is to add better negative examples: hands visible, ordinary movement, not ASL signing, especially movements that can look like HELLO.

This is not another one-word recognition loop. It is a safety-floor step needed before E5-A large dual-source batch screening.

## Verified Inputs

- E4-AA base no-sign dataset: `artifacts/recognition_upgrade/e4_generalization/e4_aa_nosign_temporal_gate_01`
- E4-AC best gate: `artifacts/recognition_upgrade/e4_generalization/e4_ac_low_motion_aware_gate_01`
- E4-AD false-commit evidence: `artifacts/recognition_upgrade/e4_generalization/e4_ad_false_commit_review_01`
- E4-AF policy result: `artifacts/recognition_upgrade/e4_generalization/e4_af_acceptance_policy_01`

## New Files

- Runner: `pipeline/rgb/e4_ag_hello_like_nosign_expansion.py`
- Output folder: `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01`
- Capture guide: `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01/README_CAPTURE_GUIDE.md`
- Raw capture root: `scratchpad/e4_ag_hello_like_nosign/raw`

## Capture Folder Layout

Put videos under:

```text
scratchpad/e4_ag_hello_like_nosign/raw/p1/<participant>/<device>/<environment>/front/<video>.mp4
```

Example:

```text
scratchpad/e4_ag_hello_like_nosign/raw/p1/P03/phoneA/indoor/front/p03_hello_like_01.mp4
```

The init command already created:

```text
scratchpad/e4_ag_hello_like_nosign/raw/p1/P03/phoneA/indoor/front
```

Add more participant/device/environment folders if available.

## What To Record

Record hands visible but not signing:

- casual waving that is not ASL HELLO;
- talking gestures;
- hands near face, chest, shoulders, or side of body;
- adjusting hair, glasses, sleeves, phone, chair, or posture;
- resting hands with small movement;
- different people, phones, distances, shirts, and backgrounds.

Avoid actual ASL signs. The label is **NO_SIGN**, not HELLO.

## Recommended Amount

For this bounded pass:

- `8` to `15` clips total;
- `15` to `30` seconds per clip;
- at least `3` participants if possible;
- at least `2` phones if possible;
- front camera first.

This should be enough for a targeted safety experiment without becoming a month-long data campaign.

## User Commands

Run from project root:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
```

After recording videos, prepare the review set:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture prepare `
  --raw-root "scratchpad\e4_ag_hello_like_nosign\raw" `
  --kind p1 `
  --output "artifacts\recognition_upgrade\e2e_c0\hello_like_p1_capture_01" `
  --max-total 160
```

Review the sampled frames:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture review `
  --run-dir "artifacts\recognition_upgrade\e2e_c0\hello_like_p1_capture_01"
```

Check the review:

```powershell
.\.venv\Scripts\python.exe -m pipeline.tracking.e2e_c0_capture check `
  --run-dir "artifacts\recognition_upgrade\e2e_c0\hello_like_p1_capture_01"
```

Then prepare the expanded no-sign tensor:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_ag_hello_like_nosign_expansion prepare `
  --extra-p1-run "artifacts\recognition_upgrade\e2e_c0\hello_like_p1_capture_01" `
  --output "artifacts\recognition_upgrade\e4_generalization\e4_ag_hello_like_nosign_expansion_01"
```

Check the expanded dataset:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_ag_hello_like_nosign_expansion check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_ag_hello_like_nosign_expansion_01" `
  --require-dataset
```

Finally, train/evaluate the gate using the existing E4-AC runner:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_ac_low_motion_aware_gate run `
  --e4aa-run "artifacts\recognition_upgrade\e4_generalization\e4_ag_hello_like_nosign_expansion_01" `
  --output "artifacts\recognition_upgrade\e4_generalization\e4_ag_low_motion_gate_01"
```

Check the gate result:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_ac_low_motion_aware_gate check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_ag_low_motion_gate_01" `
  --require-metrics
```

## Expected Outputs

Capture/review output:

- `artifacts/recognition_upgrade/e2e_c0/hello_like_p1_capture_01/capture_manifest.csv`
- `artifacts/recognition_upgrade/e2e_c0/hello_like_p1_capture_01/reviewed_manifest.csv`
- `artifacts/recognition_upgrade/e2e_c0/hello_like_p1_capture_01/gold_review.csv`

Expanded dataset:

- `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01/dataset/nosign_features.npz`
- `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01/dataset/nosign_manifest.csv`
- `artifacts/recognition_upgrade/e4_generalization/e4_ag_hello_like_nosign_expansion_01/logs/dataset_summary.json`

Gate result:

- `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01/metrics/low_motion_gate_metrics.json`
- `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01/predictions/test_predictions.csv`
- `artifacts/recognition_upgrade/e4_generalization/e4_ag_low_motion_gate_01/check_report.json`

## Acceptance Gate

The retrained gate should pass:

- min accepted precision >= `0.95`;
- min positive coverage >= `0.90`;
- max no-sign false commit <= `0.05`;
- min GOOD recall >= `0.90`;
- min SORRY recall >= `0.90`;
- HELLO should be inspected manually from metrics/predictions even though the inherited E4-AC gate does not yet enforce it in code.

## Go / No-Go

If E4-AG passes:

- proceed to E5-A large dual-source candidate screening;
- still do not integrate Android/export until later device gates.

If E4-AG fails:

- do not repeat generic threshold sweeps;
- inspect whether the added negatives are too narrow or whether the signing gate representation needs redesign;
- E5-A may proceed only as research-only screening, not runtime promotion.

## Risks

- Captured clips may accidentally include real ASL signs.
- If all clips come from one person or one phone, the model may learn source-specific negatives.
- MediaPipe may make ordinary hand movement look structurally similar to HELLO.
- More no-sign data can reduce false commits but may also over-reject low-motion valid signs.

## Next Required Action

User records HELLO-like no-sign clips under `scratchpad/e4_ag_hello_like_nosign/raw`, then runs the prepare/review/check commands above.

