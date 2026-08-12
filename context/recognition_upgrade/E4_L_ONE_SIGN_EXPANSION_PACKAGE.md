# E4-L One-Sign Expansion Package

**Purpose:** Define the E4-L offline diagnostic that adds one evidence-selected local candidate sign to the E4-J reliable 3-sign core.

**Scope:** Experiment package only. This does not authorize Android integration, model export, production recognizer replacement, source dataset mutation, or many-sign expansion.

**Current status:** Prepared. Limited two-clip extraction smoke passed. Basic package check passed. Full candidate extraction and training are pending user execution.

**Last updated:** 2026-07-30.

## Verified Project References

- Runner: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_l_one_sign_expansion.py`
- Run directory: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01`
- Core source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_j_reliable_core_3sign_pilot_01`
- Candidate inventory source: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_c_local_supplementary_validation_01\validated_clip_inventory.csv`
- Package config: `pilot_config.json`
- Candidate manifest: `candidate_manifest.csv`
- Runbook: `README_RUN.md`

## Candidate Selection

E4-L adds `MAKE` to the E4-J core:

- Core: `GOOD`, `HELLO`, `SORRY`
- Candidate: `MAKE`

`MAKE` was selected over `GET`, `WELCOME2`, `HAVE`, `KNOW`, and `GO` because it has the strongest candidate-readiness evidence among the excluded two-signer Stage-E classes:

| Candidate | Rows | Signers | Warning rows | Mean hand-hit | Minimum hand-hit |
|---|---:|---:|---:|---:|---:|
| `MAKE` | 70 | 2 | 3 | 0.7258 | 0.4375 |
| `GET` | 70 | 2 | 10 | 0.6206 | 0.0000 |
| `WELCOME2` | 70 | 2 | 24 | 0.5704 | 0.0000 |
| `HAVE` | 50 | 2 | 6 | 0.6967 | 0.0000 |
| `KNOW` | 50 | 2 | 7 | 0.6464 | 0.2500 |
| `GO` | 50 | 2 | 12 | 0.5619 | 0.1429 |

## Dataset Contract

Expected after full extraction:

- Classes: `GOOD`, `HELLO`, `SORRY`, `MAKE`
- Rows: `260`
- Input shape: `[96,258]`
- Split counts: train `105`, validation `35`, test `120`

Expected per-class counts:

| Split | GOOD | HELLO | SORRY | MAKE |
|---|---:|---:|---:|---:|
| train | 15 | 45 | 15 | 30 |
| validation | 5 | 15 | 5 | 10 |
| test | 30 | 30 | 30 | 30 |

Known limitation: `MAKE` has only two signers, so its validation rows are carved from the train-side signer `3B96F6-S001`; test rows come from held-out signer `6F7328-S001`. This is an expansion diagnostic, not a production-grade signer-independent benchmark.

## Model Policy

E4-L follows E4-K:

- Branch: `conv1d_baseline` only
- Seeds: `101`, `202`, `303`
- Checkpoint policy: latest/fixed epoch only
- Epochs: `20`
- Batch size: `8`
- Learning rate: `0.0005`

`masked_tcn_pool` is intentionally excluded because E4-K rejected it for the next local expansion.

## Validation Already Completed

Prepare completed successfully.

Limited extraction smoke completed successfully:

- Attempted candidate rows: `2`
- Extracted/cached rows: `2`
- Failed rows: `0`
- Partial assembled dataset rows: `192`
- Missing candidate rows after smoke: `68`

Basic package check passed with `--require-dataset`.

The partial dataset is expected after the smoke. The full extraction command will reuse the two cached candidate clips and extract the remaining 68.

## User Commands

Run from project root:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
```

Full candidate extraction:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_l_one_sign_expansion extract-candidate `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01" `
  --require-full
```

Smoke test after full extraction:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_l_one_sign_expansion smoke `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01"
```

Full training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_l_one_sign_expansion run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_l_one_sign_expansion run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01" `
  --resume
```

Final check:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_l_one_sign_expansion check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_l_make_expansion_pilot_01" `
  --require-full-dataset `
  --require-metrics
```

## Gate

E4-L should pass only if all are true:

- Conv1D latest/fixed-epoch mean test accuracy `>=0.90`.
- Every class test accuracy `>=0.90`.
- `MAKE` test accuracy `>=0.90`.
- No predicted-class collapse across seeds.

No-go if adding `MAKE` drops any core class below `0.90`, `MAKE` itself falls below `0.90`, or validation remains saturated while held-out test collapses.

## Architecture Decisions

- Use existing `[96,258]` contract for this diagnostic.
- Reuse E4-J core features without re-extracting them.
- Extract only the new candidate sign from raw local videos.
- Use Conv1D only, because E4-K rejected TCN for this branch.
- Do not export or integrate results into Android.

## Risks

- Candidate has only two signers.
- Repeated evaluation on the same held-out signer can bias decisions.
- Success on `MAKE` does not prove scalable 236-sign readiness.
- Failure may reflect insufficient signer diversity rather than the model alone.

## Next Required Action

User runs full candidate extraction, smoke, full training, and final check. Codex then analyzes `metrics\metrics.json`, `metrics\metrics.md`, and `check_report.json`.