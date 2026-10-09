# AppHear Fingerspell V2.1 — independent result review and Project Lead handoff

Date: 2026-10-08. Saved-evidence review only. No new inference, training, export, Android installation or TEST access.

## Decision

**FINGERSPELL_V2_1_LETTER_DISCRIMINATION_SUPPORTED.** Retain epoch034 as the next experimental geometry-only candidate. The letter-focused correction provides a real held-out improvement while preserving V2 full-sequence and synthetic-missingness performance. It does not establish reliable complete spelling or isolated-letter recognition. Recommend one separately authorized export/parity/device engineering transfer, using the existing isolated FINGERSPELL integration and epoch038 rollback. Do not launch another training/architecture/decoder experiment, attach the old visual residual, or automatically install this checkpoint.

This finding does not support declaring geometry an exhausted representation. It also does not prove that geometry alone can reach the required accuracy. No automatic appearance experiment is justified by this review.

## Identity and preservation

- Research branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`; existing dirty/untracked work preserved.
- Correct Android integration baseline remains `cee71d9f181695847936eb5f3605ea37eab82a95` in the separate October4 worktree. Installed geometry-only epoch038 is unchanged.
- Selected main-only model: `runs/fingerspelling_sequence_v2_1_01/best_candidates/epoch_034.keras`.
- Selected model SHA-256: `3f92287c5ee82b2e0de1d396c4d27fe3b0efaed8af23b79b878740a56f1af638`.
- Dual-head training checkpoint SHA-256: `7ae6d97cde09e7cb5cbfadbf361562fcd7f5469ec46975df5f13052e0e2aac31`.
- Final report SHA-256: `08f6aa833ab53a3f5218e2d03fb2590c87f0f1d4d29c011418c54dc95f7ae0ab`.
- Frozen config SHA-256: `3c75a8be613ca90d2a57f4253709d8ad54304c7fb32453d406c27266e061409e`.
- epoch038 reference SHA-256: `b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886`.
- V2 epoch046 reference/warm-start SHA-256: `88a92131eb07ce97b18f2ad4b9ea8d927858c1582177b5a04105a361e071c96a`.
- Confirmation lock, completion, selected main/training models, run configuration and all recorded code hashes agree. Adapter v1 identity remains frozen at `[T,405]`.
- All 1,598 protected files match the pre-V2.1 inventory, including protected Android/WORD/perception and existing reference packages. No behavioral WORD regression run is claimed: no runtime was edited or installed.

## Architecture and training

The unchanged V2 symmetric masked TCN has64 channels, two kernel3 convolutions per residual block, eight dilation blocks1/2/4/8/16/32/64/128, stride1, RF1021 and292,956 main-inference parameters. A training-only Dense64→27 head after block4/RF61 adds1,755 parameters; total294,711. Its target removes only SPACE, preserving all letters/repeats. Fixed loss = main CTC +0.5×letters-only auxiliary CTC; auxiliary blank26, main blank27. No pseudo boundaries, class weighting, S-specific correction or new data.

Warm-started exact V2 epoch046 with fresh Adam, unchanged LR0.001, batch8, seed20261007 and four native/intermediate/phone/phone_robust regimes. Local losses are engineering training objectives, not held-out accuracy.

| Epoch | Main TRAIN CTC | Auxiliary TRAIN CTC | Total TRAIN loss | DEV-A four-term raw-greedy selection |
|---|---:|---:|---:|---:|
| 1 | 29.4157 | 39.0433 | 48.9373 | 46.05% |
| 34 | 26.9969 | 22.8677 | 38.4307 | 41.78% |
| 49 | 26.3360 | 22.1624 | 37.4172 | 42.25% |

49 complete epochs,25,088 optimizer updates=49×512. Epoch034 is the first minimum of the frozen equal native-full/phone-full/native-no-SPACE/phone-no-SPACE DEV-A raw-greedy score. Stopped after15 epochs without the required anchor improvement. All49 epoch selections were independently recomputed; all4096 unique TRAIN samples retained each epoch, finite main/auxiliary/total losses, valid masks/adapter lineage/CTC fallback and no timestep deletion in robustness records. Actual fallback includes denser robust regimes when phone CTC capacity is insufficient.

FP32 batch-loss addition versus independently accumulated epoch means differs by at most 1.14e-07; this is numerical accumulation, not a loss-weight change. Edit metrics/selection were checked to1e-12.

The41.78% training selection score is not final beam CER and is not comparable to V2’s earlier two-term selection score. Final inference is unchanged beam10, blank27, penalty0.5, Top-1; no decoder tuning.

Prior TRAIN-only engineering evidence: six-example overfit main6/6/local6/6 exact after175updates, both head gradients finite/useful; late blocks5–8 are not connected to auxiliary output. Main-only inference excludes auxiliary operations. No trained epoch034 TFLite/Android parity is claimed here.

RF61 is61 observations, not61ms or a linguistic letter.509/512 sparse DEV sequences haveT<=61,335/512T<=31. Thus auxiliary context can cover much/all of many sparse clips; it is letters-only sequence supervision, not direct reviewed letter timing. Auxiliary loss, extra warm-start fitting and letter-aware selection changed together, so their separate causal effects are not identified.

## Normal DEV — full transcript including SPACE

CER lower is better. These are offline signer-held-out sequence diagnostics, not live phone accuracy.

| Cohort/view | epoch038 CER | V2 CER | V2.1 CER | V2.1 change vs V2 (pp) |
|---|---:|---:|---:|---:|
| dev_a/native | 42.75% | 40.27% | 37.84% | -2.43 |
| dev_a/phone | 46.98% | 43.48% | 41.91% | -1.56 |
| dev_b/native | 41.88% | 37.61% | 35.36% | -2.25 |
| dev_b/phone | 46.24% | 42.71% | 40.01% | -2.70 |

| Cohort/view/model | S / D / I | Correct aligned symbols | Predicted chars | Precision | Predicted/reference | Exact /256 |
|---|---|---:|---:|---:|---:|---:|
| dev_a/native/epoch038 | 513/801/164 | 2143 | 2820 | 75.99% | 0.816 | 0 |
| dev_a/native/V2 epoch046 | 585/587/220 | 2285 | 3090 | 73.95% | 0.894 | 1 |
| dev_a/native/V2.1 epoch034 | 488/602/218 | 2367 | 3073 | 77.03% | 0.889 | 2 |
| dev_a/phone/epoch038 | 771/686/167 | 2000 | 2938 | 68.07% | 0.850 | 1 |
| dev_a/phone/V2 epoch046 | 744/614/145 | 2099 | 2988 | 70.25% | 0.864 | 2 |
| dev_a/phone/V2.1 epoch034 | 727/582/140 | 2148 | 3015 | 71.24% | 0.872 | 1 |
| dev_b/native/epoch038 | 543/720/150 | 2111 | 2804 | 75.29% | 0.831 | 2 |
| dev_b/native/V2 epoch046 | 502/572/195 | 2300 | 2997 | 76.74% | 0.888 | 3 |
| dev_b/native/V2.1 epoch034 | 442/568/183 | 2364 | 2989 | 79.09% | 0.886 | 7 |
| dev_b/phone/epoch038 | 746/659/155 | 1969 | 2870 | 68.61% | 0.851 | 1 |
| dev_b/phone/V2 epoch046 | 702/613/126 | 2059 | 2887 | 71.32% | 0.856 | 2 |
| dev_b/phone/V2.1 epoch034 | 629/596/125 | 2149 | 2903 | 74.03% | 0.860 | 5 |

Both phone cohorts improve S/D/I and precision versus V2. Native DEV-A substitutions fall97 but deletions rise15; native DEV-B all three error counts fall. V2.1 has one native DEV-B empty prediction, while V2 has none; phone empty counts are zero for both. DEV-A phone exact strings regress2→1; DEV-B improves2→5. These individual regressions are preserved rather than hidden by aggregate CER.

## Letter discrimination and single-word evidence

| Cohort/view | No-SPACE CER epoch038 / V2 / V2.1 | Single-word CER epoch038 / V2 / V2.1 |
|---|---|---|
| dev_a/native | 40.13% / 38.56% / 35.24% | 41.63% / 45.71% / 39.18% |
| dev_a/phone | 45.07% / 42.94% / 41.03% | 48.57% / 48.16% / 42.86% |
| dev_b/native | 38.93% / 35.44% / 33.00% | 48.28% / 49.43% / 42.53% |
| dev_b/phone | 44.67% / 42.42% / 39.41% | 48.85% / 52.30% / 47.13% |

| Pooled phone metric | epoch038 | V2 | V2.1 |
|---|---:|---:|---:|
| Full CER | 46.61% | 43.10% | 40.97% |
| No-SPACE CER | 44.87% | 42.69% | 40.23% |
| Aligned letters /6316 | 3737 | 3800 | 3989 |
| Original-alignment letter recall | 59.17% | 60.16% | 63.16% |
| SPACE correct /515 | 232 | 358 | 308 |
| Full S/D/I | 1517/1345/322 | 1446/1227/271 | 1356/1178/265 |
| Full precision | 68.34% | 70.77% | 72.61% |
| Exact full strings /512 | 2 | 4 | 6 |
| Single-word CER (42 sequences/419 chars) | 48.69% | 49.88% | 44.63% |
| Single-word correct chars | 253 | 242 | 269 |
| Single-word S/D/I | 111/55/38 | 131/46/32 | 104/46/37 |
| Single-word precision | 62.94% | 59.75% | 65.61% |
| Single-word exact /42 | 1 | 1 | 1 |

Versus V2,139 more full-alignment matches comprise **189 more letters and50 fewer spaces**. This is qualitatively different from V2’s SPACE-dominated improvement. Original letter recall improves2.99 absolute pp (60.16→63.16%); pooled no-SPACE CER improves2.45pp. No-SPACE rescoring removes spaces then realigns; it is distinct from original-alignment letter recall and yields3998 correct letters, not3989.

Single-word membership is exactly the prior frozen diagnostic42 IDs. Phone CER improves5.25pp versus V2 and4.06pp versus epoch038, correct letters242→269, substitutions131→104, deletions46→46, insertions32→37, precision59.75→65.61%. All four cohort/view single-word CERs improve versus both references. Phone exact single-word strings remain1/42, so the gain does not establish reliable names; no isolated-letter test exists in these sets.

## Per-letter recall — pooled phone, original edit alignment

| Letter | References | epoch038 correct / recall | V2 correct / recall | V2.1 correct / recall | Δ vs epoch038 pp | Δ vs V2 pp |
|---|---:|---|---|---|---:|---:|
| A | 760 | 590 / 77.63% | 577 / 75.92% | 618 / 81.32% | +3.68 | +5.39 |
| B | 128 | 78 / 60.94% | 82 / 64.06% | 92 / 71.88% | +10.94 | +7.81 |
| C | 233 | 135 / 57.94% | 121 / 51.93% | 146 / 62.66% | +4.72 | +10.73 |
| D | 194 | 73 / 37.63% | 79 / 40.72% | 75 / 38.66% | +1.03 | -2.06 |
| E | 670 | 404 / 60.30% | 421 / 62.84% | 466 / 69.55% | +9.25 | +6.72 |
| F | 62 | 31 / 50.00% | 34 / 54.84% | 29 / 46.77% | -3.23 | -8.06 |
| G | 139 | 60 / 43.17% | 66 / 47.48% | 81 / 58.27% | +15.11 | +10.79 |
| H | 180 | 125 / 69.44% | 145 / 80.56% | 140 / 77.78% | +8.33 | -2.78 |
| I | 424 | 314 / 74.06% | 321 / 75.71% | 330 / 77.83% | +3.77 | +2.12 |
| J | 127 | 69 / 54.33% | 67 / 52.76% | 80 / 62.99% | +8.66 | +10.24 |
| K | 96 | 48 / 50.00% | 53 / 55.21% | 49 / 51.04% | +1.04 | -4.17 |
| L | 405 | 185 / 45.68% | 165 / 40.74% | 191 / 47.16% | +1.48 | +6.42 |
| M | 171 | 84 / 49.12% | 102 / 59.65% | 81 / 47.37% | -1.75 | -12.28 |
| N | 578 | 380 / 65.74% | 385 / 66.61% | 396 / 68.51% | +2.77 | +1.90 |
| O | 425 | 261 / 61.41% | 285 / 67.06% | 247 / 58.12% | -3.29 | -8.94 |
| P | 91 | 38 / 41.76% | 40 / 43.96% | 42 / 46.15% | +4.40 | +2.20 |
| Q | 17 | 3 / 17.65% | 3 / 17.65% | 4 / 23.53% | +5.88 | +5.88 |
| R | 481 | 280 / 58.21% | 304 / 63.20% | 297 / 61.75% | +3.53 | -1.46 |
| S | 340 | 235 / 69.12% | 150 / 44.12% | 219 / 64.41% | -4.71 | +20.29 |
| T | 282 | 166 / 58.87% | 189 / 67.02% | 172 / 60.99% | +2.13 | -6.03 |
| U | 144 | 38 / 26.39% | 58 / 40.28% | 62 / 43.06% | +16.67 | +2.78 |
| V | 75 | 22 / 29.33% | 23 / 30.67% | 27 / 36.00% | +6.67 | +5.33 |
| W | 77 | 39 / 50.65% | 45 / 58.44% | 43 / 55.84% | +5.19 | -2.60 |
| X | 19 | 6 / 31.58% | 3 / 15.79% | 6 / 31.58% | +0.00 | +15.79 |
| Y | 114 | 41 / 35.96% | 53 / 46.49% | 48 / 42.11% | +6.14 | -4.39 |
| Z | 84 | 32 / 38.10% | 29 / 34.52% | 48 / 57.14% | +19.05 | +22.62 |

**Common-character safeguard: no failures.** Applied unchanged to every letter with>=100 pooled phone references and a>10pp regression versus epoch038.21letters improve versus epoch038,4regress(F/M/O/S),X ties. Versus V2,16 improve and10 regress. S recovers150/340→219/340 (44.12→64.41%) but remains below epoch038235/340 (69.12%). M regresses102→81 (-12.28pp), O285→247 (-8.94pp), T189→172 (-6.03pp) versus V2; their epoch038 comparisons are much smaller or positive. Passing the frozen safeguard does not mean every letter improved.

Poor classes remain: D38.66%, L47.16%, M47.37%, U43.06%, Y42.11%; Q4/17 andX6/19 have particularly weak/low-support estimates. These are sequence-alignment recalls, not frame-level handshape classification accuracy. No heuristic/class-specific tuning follows.

## Signer spread and sequence directions

| Cohort/view | Signers improve/regress/tie vs epoch038 | vs V2 | Sequences improve/regress/tie vs epoch038 | vs V2 |
|---|---|---|---|---|
| dev_a/native | 14/1/0 | 9/4/2 | 138/59/59 | 112/70/74 |
| dev_a/phone | 14/1/0 | 11/3/1 | 139/54/63 | 98/76/82 |
| dev_b/native | 15/0/0 | 12/3/0 | 153/49/54 | 108/66/82 |
| dev_b/phone | 14/1/0 | 10/4/1 | 146/48/62 | 108/65/83 |

| Signer | A phone epoch038 / V2 / V2.1 CER | B phone epoch038 / V2 / V2.1 CER |
|---|---|---|
| 001e | 47.21% / 39.91% / 40.77% | 43.29% / 38.53% / 32.90% |
| 1c15 | 40.71% / 39.38% / 39.38% | 42.27% / 44.55% / 39.09% |
| 28d4 | 37.67% / 28.84% / 32.56% | 31.22% / 24.88% / 27.80% |
| 2b19 | 56.77% / 55.02% / 51.53% | 52.97% / 50.23% / 43.84% |
| 4e6b | 48.44% / 44.00% / 42.22% | 52.34% / 48.13% / 43.46% |
| 5ce0 | 56.05% / 56.05% / 54.84% | 51.50% / 54.51% / 53.01% |
| 661f | 34.32% / 28.81% / 27.97% | 38.71% / 38.25% / 30.41% |
| a459 | 38.77% / 33.04% / 32.60% | 33.63% / 30.09% / 33.19% |
| aeed | 44.77% / 42.68% / 35.98% | 47.24% / 42.13% / 38.98% |
| c28d | 65.90% / 60.83% / 56.68% | 68.10% / 60.95% / 63.33% |
| c6e5 | 58.33% / 53.57% / 52.78% | 64.52% / 53.92% / 54.84% |
| d516 | 47.37% / 44.74% / 42.98% | 45.91% / 43.18% / 37.27% |
| d5fd | 40.09% / 41.85% / 36.56% | 42.17% / 37.83% / 36.52% |
| ebdb | 47.77% / 43.30% / 39.73% | 41.18% / 37.39% / 30.25% |
| f896 | 39.39% / 38.53% / 40.69% | 38.16% / 34.30% / 34.30% |

Phone macro signer CER: A46.90→43.37→41.82%; B46.21→42.59→39.95%. Improvements are broad versus epoch038 and a majority versus V2; not universal. The worst pooled signers and individual difficult words remain unresolved. DEV-A andDEV-B share the same15 official DEV signers, so these cohorts are not30 independent signers.

## J/Z/repeated-letter groups — full sequence CER

| Cohort/view/group | Sequences | epoch038 / V2 / V2.1 CER |
|---|---:|---|
| dev_a/native/J | 59 | 43.60% / 40.80% / 36.53% |
| dev_a/native/Z | 52 | 43.31% / 42.07% / 37.93% |
| dev_a/native/REPEATED_LETTERS | 109 | 43.17% / 40.25% / 38.79% |
| dev_a/phone/J | 59 | 48.53% / 45.47% / 42.93% |
| dev_a/phone/Z | 52 | 49.52% / 44.00% / 38.90% |
| dev_a/phone/REPEATED_LETTERS | 109 | 47.35% / 44.16% / 43.50% |
| dev_b/native/J | 61 | 42.66% / 39.55% / 36.44% |
| dev_b/native/Z | 25 | 38.86% / 28.86% / 27.14% |
| dev_b/native/REPEATED_LETTERS | 110 | 45.48% / 41.34% / 38.44% |
| dev_b/phone/J | 61 | 47.14% / 42.91% / 39.80% |
| dev_b/phone/Z | 25 | 41.71% / 35.14% / 29.71% |
| dev_b/phone/REPEATED_LETTERS | 110 | 49.90% / 46.10% / 44.51% |

All12 full subgroup CERs improve versus V2 and epoch038. Pooled J recall67/127→80/127; Z29/84→48/84 versus V2, now also above epoch03869/127 and32/84. Group CER and individual-letter recall are separate evidence. Repeated-letter exact strings remain rare; no special decoder rules were added.

## Frozen synthetic-missingness stress

| Cohort/view | epoch038 / V2 / V2.1 CER | V2 S/D/I → V2.1 | V2 precision → V2.1 | Extra CER above own normal phone V2 → V2.1 pp |
|---|---|---|---|---|
| dev_a/stress_moderate | 52.16% / 48.94% / 46.92% | 843/709/140 → 804/701/117 | 65.96% → 67.94% | 5.47 → 5.00 |
| dev_a/stress_heavy | 59.97% / 55.34% / 53.80% | 936/893/84 → 880/892/88 | 61.48% → 63.51% | 11.86 → 11.89 |
| dev_a/stress_contiguous | 53.66% / 48.37% / 46.80% | 843/705/124 → 774/730/114 | 66.38% → 68.74% | 4.89 → 4.89 |
| dev_b/stress_moderate | 52.40% / 48.31% / 46.24% | 805/715/110 → 746/710/104 | 66.96% → 69.29% | 5.60 → 6.22 |
| dev_b/stress_heavy | 59.28% / 54.83% / 52.90% | 874/893/83 → 776/929/80 | 62.68% → 66.10% | 12.12 → 12.89 |
| dev_b/stress_contiguous | 52.87% / 48.78% / 46.59% | 806/739/101 → 706/753/113 | 66.85% → 70.04% | 6.08 → 6.58 |

All six absolute stress CERs improve and all six precisions improve versus V2. Robustness is retained, not solved. Heavy DEV-B deletions rise893→929; contiguous deletions rise A705→730/B739→753. Relative degradation versus each model’s normal phone result is not uniformly smaller; heavy/contiguous DEV-B sensitivity increases. These masks withdraw evidence from real observations with preserved timesteps, not a measured CameraX simulator.

## Representative paired phone predictions

Mechanically selected strongest improvements/regressions versus V2 by edit-count delta, then sample ID; illustrative only, not an extra evaluation set.

| Cohort/reference | epoch038 | V2 | V2.1 | Error Δ vs V2 |
|---|---|---|---|---:|
| dev_a: `LESLIE HAHN` | `JEALIE ANA` | `EARIE AMT` | `EALRIE HAHN` | -3 |
| dev_a: `CLINICALSUPPLYCOMPANY` | `JRINI A SRAIY OMOMPANIY` | `RNIA ER TI OMOMPNIY` | `RSNIASRQ TYJOMPNIY` | -3 |
| dev_a: `CORAL SPRINGS FLORIDA` | `ZCORAZ USPRIGES CFLSRIDS` | `CORAT UTPRIG S CBLORIUDS` | `GCORAT GCUGSTPRIGAS CBLARIDS` | +4 |
| dev_a: `STAR POWELL` | `S PWEL` | `SAR POMWEL` | `SEPEMWEL` | +4 |
| dev_b: `WEST COVINA CALIFORNIA` | `WESD ONVIACALRIA` | `WETCONVI AYMVIA` | `WES CONVIACALIRIA` | -5 |
| dev_b: `DOMINGO CHRISTENSEN` | `DOMN E HCSTN EN` | `MADONH HIATNTENT` | `ADONT CHISTNEN` | -4 |
| dev_b: `SANTA ROSA CALIFORNIA` | `SANAROSACALIUNSA` | `ANTARO ACALIORNIA` | `ANARMNACALIRNIA` | +3 |
| dev_b: `HUNTINGTON BEACH CA` | `HRINGON A RCA` | `HRNINGENBA CA` | `TRINGANBAECA` | +3 |

## Verification, limitations and next step

- Independently recomputed90 final full/no-SPACE/single-word score records, including subgroup/signer counts and original character alignments. All 1,536 final stress-lineage records exactly reproduce the frozen V2 masks with unchanged timesteps. Exact agreement with saved metrics; no model inference rerun.
- Verified all10 cohort/view groups (30 model records) have identical256 IDs, signers, transcripts, timestep lengths andCTC headroom. Both reference predictions exactly reproduce historical V2-review predictions in every original/stress view.
- Verified4096TRAIN/256DEV-A/256DEV-B,117TRAINsigners/15DEVsigners, official role separation and unique source identity from existing frozen metadata.42single-word membership exactly retained.
- Verified all49 epoch records: correct four-term first-minimum selection, finite loss, all4096TRAIN IDs/cadence lineage/adapter identities and robust withdrawal budgets. No DEV-B checkpoint selection or TEST flags. Confirmation lock is created before DEV-B inference in the reviewed evaluator code.
- 28 focused V2.1 target/selection and prefix-beam tests pass; Ruff and mypy pass for the new evidence-audit utility. A pyreadline console-destructor warning occurred after pytest success; exit code0 and all28tests completed. No test failure or model error is inferred from that shutdown warning.
- 1,598 protected hashes unchanged. Existing WORD, Candidate01, raw-v1, Adapter v1, Context Assist, Android and old models/packages remain unchanged. No export/install/retrain is performed.

Known: letter-oriented training/selection improves held-out letter and single-word diagnostics on these fixed cohorts; SPACE-only gains no longer explain progress. No common-character safeguard fails.

Supported interpretation: supervision/selection had left useful geometry information underexploited. This narrows the prior discrimination diagnosis; it does not prove the precise physical causes of each confused handshape or uniquely attribute gains to the auxiliary head.

Unknown: proficient-signer live accuracy, isolated A–Z accuracy, exact phone-domain letter timing/perception cause, trained epoch034 Keras→TFLite→Android parity/runtime. Current no-expert phone attempts remain engineering smoke, never training labels or quality benchmarks. DEV-B is previously opened post-lock confirmation, shares signers with DEV-A, and must not become a tuning loop. TEST remains sealed.

**Next recommended action:** review/authorize export and isolated device transfer of the exact main-only epoch034 geometry candidate. Reuse existing FP32 export/masking/beam10/.5/Start–Done–Preview framework, preserve epoch038 rollback, and verify numerical/text parity before install. Do not copy the auxiliary head into Android, use old residual weights, tune another decoder, or promise reliable single letters. Do not start V2.2/V3 or visual training from this review.

New review files:
- `tools/fingerspelling/sequence_v2_1_result_review.py` — reproducible saved-evidence validation; noTensorFlow/inference/training.
- `artifacts/fingerspelling_sequence_v2_1_review_01/analysis.json` — verified comparisons/history/hashes/governance.
- `docs/apphear-fingerspelling-sequence-v2-1-result-review-2026-10-08.md` — this handoff.
- Append-only completion/decision entries in `context/progress-tracker.md` and `memory.md`.

Reproduce: `.\.venv\Scripts\python.exe -m tools.fingerspelling.sequence_v2_1_result_review`.

FINGERSPELL_V2_1_LETTER_DISCRIMINATION_SUPPORTED
