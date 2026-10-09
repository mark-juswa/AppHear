# AppHear fingerspelling TRAIN-4096 / DEV-B plan 01

Date: 2026-10-05. Status: `TRAIN4096_PLAN_READY`. Metadata/manifests only; no RGB acquisition, Candidate01 extraction, inference, training, Android build or TEST payload access occurred. Existing model, decoder and runtime contracts remain unchanged.

## Repository and preservation

- Research branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Application baseline `baseline/apphear-text-to-asl-context-assist-ui-2026-10-04` at `cee71d9f181695847936eb5f3605ea37eab82a95`; actual Android worktree remains the isolated October 4 checkout. Older protected WORD baseline `76d93cecd85bf9f76064d320aa4a5791b5f0704a` remains preserved.
- Existing dirty/untracked work is recorded in `artifacts/fingerspelling_train4096_plan_01/starting_git_status.txt`. No reset, merge, branch switch, unrelated overwrite or deletion.
- Rehashed all 8,223 inventoried existing files (10,322,091,704 bytes), including original dataset sources/raw/features, model runs, decoder/Android evidence and protected source inventories: **zero changed/missing files**. Evidence `preservation_before.json` and `preservation_result.json`.

## Governing identities and deterministic method

- Original foundation manifest SHA-256 `6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e`. Original DEV overlap policy SHA-256 `e029b1e2fb698ce53d810adf0d475d28697bd8394450876e2308c759dabdbb28`.
- Pinned official FSboard v13 metadata: DAUN train, MacKenzie train and DAUN validation. Existing authorized DAUN TEST metadata is read only for the unchanged normalized-phrase exclusion and protected-MD5-copy checks. No TEST RGB or model performance accessed.
- Metadata paths and full hashes are retained in every manifest `metadata_sources`. This plan requires those same bytes, the frozen adapter identity, original selector SHA and original bounded runner SHA.
- Reused `pipeline/fingerspelling/sequence_manifest.py::select_balanced`, original salt `apphear-fsboard-foundation-01-v1`, original signer round-robin and buckets: short <=11, medium 12–20, long >=21; tags J, then Z, then repeated, then ordinary. Within buckets the original salted filename-hash ordering is retained.
- Force every existing TRAIN filename into selection, then extend each stratum to 2,048. Keep the original 1,024 complete rows and order first; append the 3,072 selected additions. No selection by Candidate01 success, logits, loss, crop quality or DEV results.
- No prior extension policy exists beyond the selector’s forced-row mechanism. No governance conflict prevents 2,048 DAUN + 2,048 MacKenzie. Eligible alphabet TRAIN pools: DAUN 8,906 and MacKenzie 55,504. Human IDs shared across strata remain one human, not two signers.
- DEV-B is selected by the same selector from eligible official DEV after the unchanged DEV/TEST phrase exclusions and removal of all DEV-A sequence IDs. Eligible DEV 1,371; remaining outside DEV-A 1,115, all 15 signers retained.
- Q/X do not have special quotas in the existing selector. Their coverage increases naturally: Q 20 ->105 and X 28 ->132. No new sampling heuristic was introduced.

## Frozen manifests

| Artifact | SHA-256 |
|---|---|
| `datasets/fingerspelling/train4096_plan_01/train4096_manifest.json` | `4dd03d43b2f6e2e9a7b83fa21b0a5f65cd92f460e52e197f94f1929dfd11bbbb` |
| `datasets/fingerspelling/train4096_plan_01/train_additions/tranche_manifest.json` | `8f219a84dee854422de5ed138512d6cd5fcc258a94fcf4cbc5f4c1b1a9bd5075` |
| `datasets/fingerspelling/train4096_plan_01/dev_b/tranche_manifest.json` | `50bc3cf42bc549f41ecce7f74bda0acad4be59c0b490d0afd49ec83e94efa09e` |
| `datasets/fingerspelling/train4096_plan_01/dev_a_reference.json` | `db46403dee9be51a8000420977772585b0061c53fe6faeb8c5c8f61f00ccdb4f` |
| `datasets/fingerspelling/train4096_plan_01/dev_b_policy.json` | `e3c16ffccefbe8088e69d7f3bfdd6696dae6784972f73595d23c46e1c12dab58` |

Selection config SHA-256 `61c563ee8aa09b5e6fcd889d819d4ad8174281e3930416a756d3f2ba24e430f4`. Combined batch-plan SHA-256 `9559b504d6e12a25bfaae010b92b823865f6a6c80e21d3b0cc42353e5cd906c8`.

## Coverage — verified from selected metadata

| Quantity | TRAIN-4096 | DEV-A unchanged | DEV-B confirmation |
|---|---:|---:|---:|
| Sequences | 4,096 | 256 | 256 |
| Unique official signers | 117 | 15 | 15 |
| Transcript characters, including SPACE | 76,985 | 3,457 | 3,374 |
| J-containing sequences | 1,024 | 59 | 61 |
| Z-containing sequences | 781 | 52 | 25 |
| Adjacent repeated-letter sequences | 1,711 | 109 | 110 |
| Source bytes | 29,146,915,994 | 1,578,716,662 | 1,537,451,741 |
| Sequences per signer: min / median / max | 5 / 28 / 52 | 17 / 17 / 18 | 17 / 17 / 18 |
| Transcript length: min / median / max | 3 / 17.0 / 43 | 4 / 13.0 / 31 | 6 / 13.0 / 22 |
| Short <=11 | 934 | 107 | 86 |
| Medium 12–20 | 1927 | 123 | 162 |
| Long >=21 | 1235 | 26 | 8 |
| DAUN / MacKenzie | 2,048 / 2,048 | 256 / 0 | 256 / 0 |

All 27 transcript classes occur in TRAIN-4096 and DEV-B. CTC blank 27 remains a loss/decoder class, not a transcript. Adjacent-repeat accounting preserves literal spaces; these selected cohorts happen to have equal repeated-letter and any-adjacent-repeat sequence counts. Full exact transcript-length histograms and per-signer counts are in `coverage_and_workload.json`.

## Character frequency

| Character | TRAIN-4096 | DEV-A | DEV-B |
|---|---:|---:|---:|
| A | 6,299 | 375 | 385 |
| B | 1,154 | 68 | 60 |
| C | 1,784 | 116 | 117 |
| D | 2,022 | 100 | 94 |
| E | 7,799 | 335 | 335 |
| F | 1,178 | 27 | 35 |
| G | 1,507 | 60 | 79 |
| H | 2,818 | 84 | 96 |
| I | 4,632 | 205 | 219 |
| J | 1,038 | 62 | 65 |
| K | 936 | 53 | 43 |
| L | 2,752 | 202 | 203 |
| M | 1,646 | 84 | 87 |
| N | 5,025 | 302 | 276 |
| O | 5,517 | 216 | 209 |
| P | 1,278 | 50 | 41 |
| Q | 105 | 11 | 6 |
| R | 4,472 | 231 | 250 |
| S | 3,911 | 160 | 180 |
| T | 4,558 | 155 | 127 |
| U | 2,026 | 83 | 61 |
| V | 691 | 42 | 33 |
| W | 1,227 | 44 | 33 |
| X | 132 | 10 | 9 |
| Y | 1,533 | 62 | 52 |
| Z | 831 | 58 | 26 |
| SPACE | 10,114 | 262 | 253 |

Selection tags (mutually exclusive original priority): TRAIN_4096: J=1024, Z_NO_J=754, REPEAT_NO_JZ=1166, ORDINARY_NO_JZ_REPEAT=1152; DEV_B: J=61, REPEAT_NO_JZ=82, ORDINARY_NO_JZ_REPEAT=94, Z_NO_J=19. J/Z/repeat rows in the coverage table are overlapping flags, not these exclusive tags.

## DEV-B governance and limitations

- Exactly 256 fresh sequence IDs; zero ID overlap with DEV-A or TRAIN. All 4,608 TRAIN/DEV-A/DEV-B identities and official MD5s are unique. Official signer roles remain disjoint between TRAIN and DEV.
- DEV-B vs TRAIN-4096: zero normalized phrase overlap. DEV-B vs DEV-A: 10 distinct normalized phrases shared across 12 DEV-B sequences. No new phrase-disjoint rule was invented; existing DEV/TEST exclusion remains exact.
- DEV-B uses the same 15 official DEV humans as DEV-A. It is fresh sequence-level confirmation, **not a fresh signer test or a claim of statistical independence**. Official DEV contains DAUN only.
- `dev_b_policy.json` freezes final-confirmation-only use and forbids checkpoint, hyperparameter, decoder, early-stopping and model selection. No current model/config JSON references the new DEV-B package. Future loader/config work must preserve that prohibition. Evaluate DEV-B only after all run choices and the final checkpoint are frozen.
- TRAIN contains all 117 original official TRAIN signers; expansion adds examples, not new humans. Signer `b16e` has only five eligible alphabet TRAIN clips and all five remain included, explaining the overall minimum. Stratum quotas can give signers represented in both strata more examples; that is the original balancing policy.

## Acquisition and immutable reuse

| Cohort | New videos | Exact new RGB bytes | Existing reusable videos | Candidate01 estimate | New features / raw estimate bytes |
|---|---:|---:|---:|---:|---:|
| TRAIN additions | 3,072 | 22,093,890,153 | 0 | 12.53 hours | 437,435,781 / 295,021,798 |
| DEV-B | 256 | 1,537,451,741 | 0 | 0.84 hours | 29,200,287 / 19,693,682 |
| Existing TRAIN | 0 | 0 | 1,024 | No rerun | Immutable originals |

New total: **3,328 videos / 23,631,341,894 bytes (23.63 decimal GB)**. Existing TRAIN sources: 1,024 / 7,053,025,841 bytes, all verified size + official MD5 + locally computed SHA-256 against receipts. DEV-A remains 256 / 1,578,716,662 bytes in the original package. In all, the original 1,280 sources remain reusable/preserved; no newly selected source was found cached in the frozen scan roots.
- `cached_sources.json` names every reusable source and verified hashes. `reuse_inventory.json` names original TRAIN raw/features and receipts, with hash checks and the rule `REFERENCE_IMMUTABLE_ARTIFACT_NO_COPY_OR_RECEIPT_REWRITE`.
- Original receipts bind the original foundation manifest hash. Do not copy them into the expanded package, rewrite their identity or re-extract old sources. The logical full TRAIN manifest references existing artifacts through the reuse inventory; only additions get new package receipts.

## Extraction/storage estimates — not measured new processing

- Measured existing archive inventory: 1,280 sequences, 217,221 frames, compressed geometry features 168,643,714 bytes and raw-v1 113,739,145 bytes.
- Actual timing available in 1,268 receipts: 17202.40 seconds; weighted throughput 12.494 frames/processing-second. Twelve older receipts have no comparable wall-time field and are excluded from the timing ratio.
- Observed frames/metadata-second 29.9634. Estimated new work 601,049 frames, 13.36 Candidate01 hours on the same host/distribution.
- Estimated additional compact archives: features 466,636,067 bytes; raw 314,715,480 bytes. Estimates exclude receipts/logs, extra validation reads, model startup, download time, retries and any future visual artifacts. Source duration is publisher metadata, not newly decoded duration.
- Conservative execution guard: 25,486,435,265 bytes (~25.49 decimal GB) free, including unchanged 1,073,741,824-byte reserve. About 14.03 GB is currently free on F:. Free at least another 11.46 GB before execution; more margin is prudent. No cleanup/deletion performed or automated.
- On resume, the wrapper deducts completed RGB only after verifying official size/MD5. It budgets only selected packages, while conservatively retaining their full small derived-archive estimate plus reserve. It never deletes files or bypasses integrity.

## Batches and preparation tooling

- New TRAIN package: 192 batches ×16 =3,072. DEV-B package: 16 batches ×16 =256. Total208 batches; no remainder batch. Original1,024 not dispatched. Per-batch IDs, roles, offsets, exact bytes and commands are frozen in the combined and per-package `batch_plan.json` files.
- `tools/fingerspelling/prepare_train4096.ps1` is a thin serial wrapper around the unchanged `tools.fingerspelling.foundation` CLI. Plan-only by default. `-Execute` runs size/MD5/SHA integrity, pinned Candidate01, raw validation, Adapter.v1 and receipts, then structural package validation. Stops at the first explicit failure; same command resumes verified artifacts. No parallel Candidate01, TEST, inference evaluation or training.
- The original `tools.fingerspelling.tranche` runner is deliberately unchanged and remains pinned to1,024/256. Do not point it at expansion artifacts.
- The unchanged foundation validator has old readiness quotas and a package-local parity-evidence requirement. New packages structurally pass but report `ready_to_train=false`; that is expected and is not weakened. This task creates a **plan**, not expanded dataset/training admission. A later authorized expanded loader/readiness gate must combine reused TRAIN + additions + original DEV-A and keep DEV-B outside training/model selection. No such trainer change is made now.

## Exact later user-run commands

Run after freeing disk space and explicitly choosing to begin acquisition/extraction. None of the `-Execute` commands below were run in this task.

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.fsboard_expansion_plan validate
# Optional plan-only display; no download/extraction:
& .\tools\fingerspelling\prepare_train4096.ps1
# Serial acquisition/extraction for both new packages; rerun same command to resume:
& .\tools\fingerspelling\prepare_train4096.ps1 -Execute
# Alternatively prepare each separately:
& .\tools\fingerspelling\prepare_train4096.ps1 -Package TRAIN_ADDITIONS -Execute
& .\tools\fingerspelling\prepare_train4096.ps1 -Package DEV_B -Execute
# Inspect explicit pending/failure and receipt counts:
Get-Content -Raw -LiteralPath 'datasets/fingerspelling/train4096_plan_01/train_additions/validation.json'
Get-Content -Raw -LiteralPath 'datasets/fingerspelling/train4096_plan_01/dev_b/validation.json'
# Final structural integrity checks (not the expanded training-admission gate):
& .\.venv\Scripts\python.exe -m tools.fingerspelling.foundation validate --output 'datasets/fingerspelling/train4096_plan_01/train_additions'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.foundation validate --output 'datasets/fingerspelling/train4096_plan_01/dev_b'
```

Do not run both ALL and per-package alternatives unless resuming/rechecking; choose one. Expected materialization: new TRAIN3,072 and DEV-B256 receipts, plus originalTRAIN1,024 and DEVA256 unchanged. Failed/pending sources stay explicit. No model training command is provided.

## Validation and bounded review

- 36 focused pytest tests passed: extension preservation/counts/reproducibility/role/source/class/repeat tampering plus original governance, missingness, chronological/raw, integrity and no-network reuse tests. Existing test that rewrites original validation.json was intentionally excluded.
- Ruff and mypy pass for new Python implementation/tests. PowerShell AST parse passes and PLAN ONLY208-batch invocation passes. No live acquisition/extraction smoke is claimed.
- Existing bounded CLI structural validation passes both new packages: zero structural errors, zero prepared new sequences,3,072/256 explicit pending sequences. Original1,280 feature artifacts remain unchanged.
- Two complete manifest generations produced identical bytes/hashes; independent validation reselects from metadata and compares exact serialized rows. Batch role/start/count/bytes and local/combined plans cross-check. All27 transcript symbols represented; original1,024 a strict subset; sequence IDs and source MD5s disjoint; no TEST payload access.
- Review: plan alignment PASS; system integrity PASS; metadata/governance gate PASS. Critical0, important0 for this planning deliverable. Operational limits: insufficient current disk, existing validator/trainer readiness scoped to oldfoundation, DEV-B same signers/partial phrases asDEV-A, minimum signer coverage limited by real pool. Training readiness is not asserted.

## Files created/changed

- New code/config: `pipeline/config/fingerspelling_expansion_4096_01.json`, `tools/fingerspelling/fsboard_expansion_plan.py`, `tools/fingerspelling/prepare_train4096.ps1`, `tests/test_fsboard_expansion_plan.py`.
- New versioned artifacts: `datasets/fingerspelling/train4096_plan_01/` manifests, policies, reference/reuse/cache inventories, batch plans, coverage/workload and isolated structural reports.
- New evidence: `artifacts/fingerspelling_train4096_plan_01/` repository/preservation/reproducibility/test/plan-only/decision reports.
- Documentation only appended: `context/feature-schema.md`, `context/progress-tracker.md`, `memory.md`; this report. No prior dataset, model, Android, WORD or Context Assist source changed.

## Complete signer distribution

| Official signer | TRAIN DAUN | TRAIN MacKenzie | TRAIN total | DEV-A | DEV-B |
|---|---:|---:|---:|---:|---:|
| 001e | 0 | 0 | 0 | 18 | 18 |
| 03ad | 23 | 29 | 52 | 0 | 0 |
| 0a77 | 0 | 29 | 29 | 0 | 0 |
| 0ba8 | 23 | 29 | 52 | 0 | 0 |
| 0bea | 23 | 29 | 52 | 0 | 0 |
| 0d7b | 23 | 0 | 23 | 0 | 0 |
| 110f | 23 | 0 | 23 | 0 | 0 |
| 13e3 | 23 | 29 | 52 | 0 | 0 |
| 163a | 23 | 29 | 52 | 0 | 0 |
| 196b | 23 | 0 | 23 | 0 | 0 |
| 19d3 | 23 | 29 | 52 | 0 | 0 |
| 1bd5 | 23 | 29 | 52 | 0 | 0 |
| 1c15 | 0 | 0 | 0 | 17 | 17 |
| 1c64 | 23 | 0 | 23 | 0 | 0 |
| 1d72 | 23 | 29 | 52 | 0 | 0 |
| 1f86 | 23 | 29 | 52 | 0 | 0 |
| 1f90 | 23 | 0 | 23 | 0 | 0 |
| 1f91 | 23 | 29 | 52 | 0 | 0 |
| 259b | 23 | 0 | 23 | 0 | 0 |
| 28d4 | 0 | 0 | 0 | 17 | 17 |
| 2a7a | 23 | 0 | 23 | 0 | 0 |
| 2b19 | 0 | 0 | 0 | 17 | 17 |
| 2f35 | 23 | 29 | 52 | 0 | 0 |
| 2ff7 | 23 | 29 | 52 | 0 | 0 |
| 39a6 | 1 | 29 | 30 | 0 | 0 |
| 39e5 | 23 | 29 | 52 | 0 | 0 |
| 3a6e | 23 | 29 | 52 | 0 | 0 |
| 3d12 | 23 | 29 | 52 | 0 | 0 |
| 3f8b | 0 | 29 | 29 | 0 | 0 |
| 46e0 | 23 | 0 | 23 | 0 | 0 |
| 494d | 23 | 29 | 52 | 0 | 0 |
| 4c3d | 23 | 29 | 52 | 0 | 0 |
| 4ddc | 0 | 29 | 29 | 0 | 0 |
| 4e6b | 0 | 0 | 0 | 17 | 17 |
| 4f1e | 23 | 29 | 52 | 0 | 0 |
| 51ee | 23 | 0 | 23 | 0 | 0 |
| 51f5 | 23 | 29 | 52 | 0 | 0 |
| 580e | 23 | 0 | 23 | 0 | 0 |
| 5b63 | 0 | 29 | 29 | 0 | 0 |
| 5ce0 | 0 | 0 | 0 | 17 | 17 |
| 5d33 | 0 | 29 | 29 | 0 | 0 |
| 63a1 | 23 | 29 | 52 | 0 | 0 |
| 661f | 0 | 0 | 0 | 17 | 17 |
| 675f | 23 | 29 | 52 | 0 | 0 |
| 6b92 | 0 | 29 | 29 | 0 | 0 |
| 6e0d | 23 | 0 | 23 | 0 | 0 |
| 6f68 | 0 | 29 | 29 | 0 | 0 |
| 711d | 23 | 29 | 52 | 0 | 0 |
| 740f | 23 | 0 | 23 | 0 | 0 |
| 7abf | 23 | 0 | 23 | 0 | 0 |
| 7c12 | 23 | 0 | 23 | 0 | 0 |
| 7f32 | 23 | 28 | 51 | 0 | 0 |
| 80fe | 23 | 28 | 51 | 0 | 0 |
| 812c | 23 | 28 | 51 | 0 | 0 |
| 851d | 23 | 0 | 23 | 0 | 0 |
| 8c4d | 0 | 28 | 28 | 0 | 0 |
| 8e3b | 23 | 28 | 51 | 0 | 0 |
| 8f6f | 23 | 0 | 23 | 0 | 0 |
| 917d | 22 | 28 | 50 | 0 | 0 |
| 92b7 | 22 | 0 | 22 | 0 | 0 |
| 92c6 | 22 | 0 | 22 | 0 | 0 |
| 99cb | 0 | 28 | 28 | 0 | 0 |
| 9b23 | 22 | 28 | 50 | 0 | 0 |
| 9d2b | 9 | 29 | 38 | 0 | 0 |
| 9e67 | 22 | 0 | 22 | 0 | 0 |
| 9ed9 | 0 | 28 | 28 | 0 | 0 |
| 9ff4 | 0 | 28 | 28 | 0 | 0 |
| a021 | 0 | 28 | 28 | 0 | 0 |
| a362 | 22 | 28 | 50 | 0 | 0 |
| a3d4 | 0 | 28 | 28 | 0 | 0 |
| a3e7 | 22 | 28 | 50 | 0 | 0 |
| a442 | 22 | 28 | 50 | 0 | 0 |
| a459 | 0 | 0 | 0 | 17 | 17 |
| a6ed | 22 | 28 | 50 | 0 | 0 |
| a72e | 22 | 0 | 22 | 0 | 0 |
| a95b | 0 | 28 | 28 | 0 | 0 |
| ab12 | 22 | 28 | 50 | 0 | 0 |
| adfa | 22 | 0 | 22 | 0 | 0 |
| aeed | 0 | 0 | 0 | 17 | 17 |
| b16e | 5 | 0 | 5 | 0 | 0 |
| b2d1 | 0 | 28 | 28 | 0 | 0 |
| b718 | 22 | 28 | 50 | 0 | 0 |
| b7fc | 22 | 0 | 22 | 0 | 0 |
| bb26 | 22 | 0 | 22 | 0 | 0 |
| bc24 | 22 | 0 | 22 | 0 | 0 |
| bd21 | 22 | 28 | 50 | 0 | 0 |
| bf49 | 22 | 0 | 22 | 0 | 0 |
| bf98 | 22 | 0 | 22 | 0 | 0 |
| c0df | 22 | 28 | 50 | 0 | 0 |
| c28d | 0 | 0 | 0 | 17 | 17 |
| c2fc | 22 | 0 | 22 | 0 | 0 |
| c371 | 22 | 0 | 22 | 0 | 0 |
| c6e5 | 0 | 0 | 0 | 17 | 17 |
| c7d4 | 22 | 0 | 22 | 0 | 0 |
| c82a | 22 | 28 | 50 | 0 | 0 |
| c9de | 22 | 0 | 22 | 0 | 0 |
| ca00 | 22 | 0 | 22 | 0 | 0 |
| ca14 | 22 | 0 | 22 | 0 | 0 |
| cf84 | 0 | 28 | 28 | 0 | 0 |
| d05c | 0 | 28 | 28 | 0 | 0 |
| d230 | 22 | 0 | 22 | 0 | 0 |
| d3ab | 22 | 28 | 50 | 0 | 0 |
| d478 | 0 | 28 | 28 | 0 | 0 |
| d516 | 0 | 0 | 0 | 17 | 17 |
| d5fd | 0 | 0 | 0 | 17 | 17 |
| d69c | 22 | 28 | 50 | 0 | 0 |
| d8ef | 22 | 0 | 22 | 0 | 0 |
| dbf9 | 0 | 28 | 28 | 0 | 0 |
| e0f7 | 0 | 28 | 28 | 0 | 0 |
| e2ca | 22 | 0 | 22 | 0 | 0 |
| e3c0 | 11 | 28 | 39 | 0 | 0 |
| e4fa | 22 | 28 | 50 | 0 | 0 |
| e96d | 22 | 0 | 22 | 0 | 0 |
| e98b | 22 | 0 | 22 | 0 | 0 |
| e9e5 | 22 | 0 | 22 | 0 | 0 |
| eac7 | 22 | 0 | 22 | 0 | 0 |
| ebdb | 0 | 0 | 0 | 17 | 17 |
| ed8e | 0 | 28 | 28 | 0 | 0 |
| ef07 | 22 | 0 | 22 | 0 | 0 |
| f066 | 22 | 28 | 50 | 0 | 0 |
| f418 | 22 | 28 | 50 | 0 | 0 |
| f608 | 22 | 0 | 22 | 0 | 0 |
| f709 | 22 | 0 | 22 | 0 | 0 |
| f760 | 22 | 28 | 50 | 0 | 0 |
| f896 | 0 | 0 | 0 | 17 | 17 |
| f9ea | 22 | 28 | 50 | 0 | 0 |
| fa10 | 0 | 28 | 28 | 0 | 0 |
| fb10 | 22 | 0 | 22 | 0 | 0 |
| fbb7 | 22 | 28 | 50 | 0 | 0 |
| fc15 | 22 | 0 | 22 | 0 | 0 |
| fe96 | 22 | 29 | 51 | 0 | 0 |
| fede | 0 | 28 | 28 | 0 | 0 |

TRAIN4096_PLAN_READY
