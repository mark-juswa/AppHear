# AppHear P5-D3 Preparation Handoff

Last updated: 2026-08-28 +08:00

## Status

P5-D3 preparation is complete. The twelve long training runs have not been started by the AI and remain assigned to the user.

The experiment measures whether recognition remains limited by current-distribution training coverage near the 100% point. It compares nested 50%, 75%, and 100% coverage under both frozen P5-D2 objectives:

- `PFCE_MATCHED`
- `CLIPCE_AGGREGATION_ALIGNED`

The six 100% P5-D2 runs are reused. Only the twelve 50%/75% runs are new.

## Frozen inputs and subsets

- Representation: `DWPOSE_REPRESENTATION_V2_238`
- Shape: `[96,238]`
- Classes: 236
- Full TRAIN: 3,926
- Primary validation: 816
- Actual 50% subset: 2,022
- Actual 75% subset: 3,029
- Actual 100% subset: 3,926
- All 236 classes are represented at every fraction.
- The subsets are exactly nested: 50% is a strict subset of 75%, which is a strict subset of 100%.
- Membership is deterministic, signer-first, and identical across objectives and seeds.

Frozen contract SHA-256:

`d7667d97dfc2af526d9dbb749c739bf7b9cc27b0a76035fa53e4ab26035444b9`

## Frozen training budget

Every new run uses:

- 12,300 optimizer updates
- batch size 32
- AdamW
- learning rate `5e-4`
- weight decay `1e-4`
- validation every 123 updates
- exactly 100 validation/checkpoint opportunities
- minimum primary-validation clip NLL checkpoint selection
- no augmentation
- no warm start
- no class weighting
- no source balancing
- no architecture or representation change

Seeds: 101, 202, 303.

## Integrity and smoke results

- D2 source hashes: verified
- D2 initialization hashes: verified
- D2 selected 100% checkpoint hashes: verified
- Nested-subset integrity: pass
- Per-class ceiling counts: pass
- No validation overlap: pass
- Deterministic shared batch scheduling: pass
- Model/initialization parity: pass
- Synthetic optimizer/checkpoint resume: pass
- Protected test accessed: no
- External data used: none
- Existing context files modified: none
- `context/progress-tracker.md`: untouched

## User training command

```powershell
Set-Location 'F:\ASL DATASET\5. Apphear3'
& '.\.venv\Scripts\python.exe' -m model.p5d3_data_coverage_curve train-all
```

Running the same command again resumes completed/partial work safely:

```powershell
& '.\.venv\Scripts\python.exe' -m model.p5d3_data_coverage_curve train-all
```

Progress is saved every 123 optimizer updates. A mid-block interruption may repeat the unfinished block from its last complete checkpoint.

## Monitoring command

```powershell
Get-ChildItem 'F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\p5_representation_v2\p5d3_data_coverage_curve_01\runs' -Filter run_state.json -Recurse |
ForEach-Object { Get-Content $_.FullName -Raw | ConvertFrom-Json } |
Format-Table fraction,objective,seed,completed_updates,validation_opportunities,status,best_validation_clip_nll
```

Each new run is complete only when:

```text
completed_updates        = 12300
validation_opportunities = 100
optimizer_iterations     = 12300
status                   = MAX_UPDATES_REACHED
```

## Finalization command

After all twelve new runs complete:

```powershell
& '.\.venv\Scripts\python.exe' -m model.p5d3_data_coverage_curve finalize
```

The final review must independently verify all run histories, optimizer counts, checkpoint selection and hashes, reused D2 points, ordinary and signer-balanced curves, 75% to 100% deltas, objective interaction, signer-blocked uncertainty, temporal failure scaling, source/context immutability, and the governed decision.

Do not execute the selected next gate automatically.

## Paths

- Runner: `model/p5d3_data_coverage_curve.py`
- Artifact directory: `artifacts/recognition_upgrade/p5_representation_v2/p5d3_data_coverage_curve_01/`
- Subset contract: `p5d3_subset_contract.json`
- Membership: `p5d3_subset_membership.csv`
- Coverage profile: `p5d3_data_coverage_profile.csv`
- Smoke results: `p5d3_smoke_tests.json`
