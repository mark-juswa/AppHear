# Experiment registry

## Phase 3 (this investigation; analysis only, no model trained)
| ID | Title | Status | Result in one line | Evidence |
|---|---|---|---|---|
| [EXP-P3-001](EXP-P3-001_error_analysis_and_funnel.md) | Error analysis and funnel | done | 60 % of recoverable correct words are lost before the classifier; 18 of the 20 weakest classes are not separable at phone cadence even on training clips | REPRODUCED / COMPUTED |
| [EXP-P3-002](EXP-P3-002_commit_gate_study.md) | Commit-gate study | done | confidence is uncalibrated (ECE 0.15–0.27); no data for per-class or per-signer floors; stability rule not supported; keep the global floor | COMPUTED |
| [EXP-P3-003](EXP-P3-003_model_contract_and_doc_drift.md) | Model contract and doc drift | done | 42/42 contract checks; one stale doc sentence | COMPUTED |
| [EXP-P3-004](EXP-P3-004_candidate_runtime_parity_and_cost.md) | Candidate parity and cost | done | blend parity 2–4e-7; ≈ 4× invocation cost on an emulator | MEASURED-EMU |
| [EXP-P3-005](EXP-P3-005_signer_separation_and_dataset_audit.md) | Signer separation and dataset audit | done | splits and calibration are signer-disjoint; phone set may overlap a TRAIN signer | COMPUTED / REPO-REPORTED |
| [EXP-P3-1xx](PLANNED.md) | five planned experiments | not run | need device, humans or external artifacts | — |

## Earlier experiments in the repository (REPO-REPORTED; not re-run here)
| Experiment | Outcome | Source |
|---|---|---|
| WORD v1 / v2 / v3 augmentation | v2 +3.0 points over frozen on DEV runtime windows; v3 neighbour context no gain | `docs/audit/WORD_ACCURACY_236_2026-10-17.md` |
| Exposure-controlled vs naive Sem-Lex enrichment | exposure control removes most of the gain; naive shifts the prior (uncovered classes −3.5 in 2 of 3 seeds) | same |
| WORD_BLEND_01 (pre-registered) | DEV runtime 41.5 → 48.6 %; Sem-Lex EVAL 29.4 → 45.8 %; end-to-end natural 29.3 → 33.5 % | same |
| WORD_BLEND_02 | hard classes 98 → 64; "WORD_BLEND_02 stays the reference" | `docs/audit/WORD_PRIORITIES_2026-10-18.md` |
| Hierarchical class/signer sampling | harmful (`SAMPLING_HARMFUL`) | `WORD_ACCURACY_236` §3 |
| Contrastive signer/cadence invariance | not supported | same |
| Sparse-only / cadence training | measured negative | `WORD_ROBUSTNESS_2026-10-18.md` |
| Open-set reject head, frozen-embedding rejection (E5-I, E6-3) | NO-GO: no operating point meets the bar without suppressing real signs | `context/recognition_upgrade/E5_I…`, `E6_3…` |
| Whole-event admission, S2-R3 Arm P | cannot reject movement without losing words; Arm P not adopted | `docs/audit/RECOGNITION_V3_CONTINUOUS_RELIABILITY_2026-10-17.md` |
| Parallel hand refinement (V3 Stage 1) | −37 % hand wall in isolation; live WORD −6.2 %; default-off | `docs/recognition-v3-stage1-validation-2026-10-15.md` |
