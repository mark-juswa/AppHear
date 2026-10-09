# AppHear Fingerspell Sequence Encoder V2 — independent result review

Date: 2026-10-07. Saved evidence only; no new model inference or training.

## Technical decision

**Retain epoch046 as a better phrase-level research candidate, but hold automatic Android/default promotion.** Keep epoch038 installed and preserved. The full-transcript gains are real and broadly distributed, but do not establish an equally broad improvement in individual letter discrimination or single-word spelling. Do not launch another training/architecture/decoder sweep from this review. Present the character and single-word regressions to the Project Lead before separately authorizing transfer of V2 as an experimental candidate.

The next decision is whether the phrase-level gain warrants a controlled export/parity/device comparison despite these known regressions. That comparison would establish engineering transfer, not repair S recognition or prove phone accuracy. No replacement or additional training is executed here.

## Identity and evaluation validity

- Research branch: `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`. Existing modified/untracked work retained.
- Android integration baseline remains `cee71d9f181695847936eb5f3605ea37eab82a95` in the separate October4 worktree. No Android edits or device actions performed.
- Selected V2: `runs/fingerspelling_sequence_v2_01/best_candidates/epoch_046.keras`; SHA-256 `88a92131eb07ce97b18f2ad4b9ea8d927858c1582177b5a04105a361e071c96a`.
- Reference: original TRAIN4096 epoch038, SHA-256 `b037e32789f523c043b46c32cdc2ea11f2f600fd35f30ecd672604b6f6947886`.
- Final report SHA-256 `10b4d7abcf71f9f96019f88199fb240ff98017a12242eb4508b2ec9687cac6f2`.
- Fixed decoder: prefix beam10, blank27, blank-logit penalty0.5, Top-1. No retuning.
- Frozen Adapter.v1 `[T,405]`, 4096 TRAIN / 256 DEV-A / 256 DEV-B. Official signer separation verified against the frozen manifests. All paired rows have the same IDs, transcripts, signers, timestep lengths and CTC headroom.
- Independently recomputed all 20 final score records (two cohorts × two models × five views). All equal stored metrics. Paired epoch038 native/phone predictions exactly reproduce its historical final report.
- Checked all47 epoch records: 4096 unique TRAIN sources retained each epoch, finite loss, DEV-A-only selection, no DEV-B selection or TEST flags. Recomputed native/phone selection CER each epoch.
- Best first-minimum checkpoint46: raw-greedy combinedCER46.7168%. Stopped47 after15 epochs without a ≥0.002 patience-anchor improvement; a tiny best-score update at46 correctly did not reset that anchor. Optimizer iterations24064 =47×512.
- Final model/config/completion/confirmation-lock hashes agree. The selected checkpoint remains046, not last checkpoint047 and not the architecture-gate smoke model.

## Normal DEV results — fixed beam, full transcript including SPACE

CER is character edit distance/reference characters; lower is better. Correct counts include SPACE. These are offline signer-held-out sequence diagnostics, not live end-to-end production accuracy.

| Cohort/view | epoch038 CER | V2 CER | Change (pp) | Correct aligned chars | Precision | Exact strings |
|---|---:|---:|---:|---:|---:|---:|
| dev_a/native | 42.75% | 40.27% | -2.49 | 2143 → 2285 | 75.99% → 73.95% | 0 → 1 /256 |
| dev_a/phone | 46.98% | 43.48% | -3.50 | 2000 → 2099 | 68.07% → 70.25% | 1 → 2 /256 |
| dev_b/native | 41.88% | 37.61% | -4.27 | 2111 → 2300 | 75.29% → 76.74% | 2 → 3 /256 |
| dev_b/phone | 46.24% | 42.71% | -3.53 | 1969 → 2059 | 68.61% → 71.32% | 1 → 2 /256 |

| Cohort/view | Substitutions | Deletions | Insertions | Predicted chars | Predicted/reference | Sequence improve/regress/tie |
|---|---:|---:|---:|---:|---:|---|
| dev_a/native | 513 → 585 | 801 → 587 | 164 → 220 | 2820 → 3090 | 0.816 → 0.894 | 115/79/62 |
| dev_a/phone | 771 → 744 | 686 → 614 | 167 → 145 | 2938 → 2988 | 0.850 → 0.864 | 131/60/65 |
| dev_b/native | 543 → 502 | 720 → 572 | 150 → 195 | 2804 → 2997 | 0.831 → 0.888 | 134/62/60 |
| dev_b/phone | 746 → 702 | 659 → 613 | 155 → 126 | 2870 → 2887 | 0.851 → 0.856 | 121/60/75 |

Both phone views improve S/D/I totals and precision. Native DEV-A is an error tradeoff: deletions decrease, but substitutions/insertions increase and precision falls. Complete strings remain rare: V2 phone only2/256 in each cohort; no reliable complete-spelling claim.

## Critical discrimination caveats

| Cohort/view | SPACE correct gain | Letter correct gain (original alignment) | CER with spaces removed: epoch038 → V2 |
|---|---:|---:|---:|
| dev_a/native | +116 | +26 | 40.13% → 38.56% |
| dev_a/phone | +59 | +40 | 45.07% → 42.94% |
| dev_b/native | +107 | +82 | 38.93% → 35.44% |
| dev_b/phone | +67 | +23 | 44.67% → 42.42% |

Across both phone cohorts, +189 correctly aligned symbols comprise +126 spaces and +63 letters. Thus two-thirds of that gain is SPACE. Original-alignment letter recall rises only from3737/6316 (59.17%) to3800/6316 (60.16%). Removing spaces before rescoring still improves letter-text CER by about2.1–2.2pp, so improvement is not purely a space artifact. The two alignments are different diagnostics and their correct counts must not be conflated.

**S is a substantial reproduced regression:** phone S recall DEV-A111/160→75/160; DEV-B124/180→75/180. Pooled235/340 (69.12%)→150/340 (44.12%). S deletions rise47→90, substitutions to A rise10→34, and substitutions to T rise3→23. S→SPACE substitutions are11→12, so direct replacement of S by SPACE does not explain the regression. These are deterministic edit-alignment outcomes, not linguistic frame-level confusions or a demonstrated implementation bug.

Single-word subgroup (no SPACE in reference), identified after results and therefore diagnostic rather than a new selection rule:

| Cohort/view | Sequences/chars | epoch038 CER | V2 CER | Correct chars | Precision |
|---|---|---:|---:|---:|---:|
| dev_a/native | 23/245 | 41.63% | 45.71% | 162 → 156 | 71.68% → 67.24% |
| dev_a/phone | 23/245 | 48.57% | 48.16% | 153 → 146 | 62.20% → 59.59% |
| dev_b/native | 19/174 | 48.28% | 49.43% | 103 → 113 | 66.88% → 66.47% |
| dev_b/phone | 19/174 | 48.85% | 52.30% | 100 → 96 | 64.10% → 60.00% |

Pooled single-word phone:42 sequences/419 chars, CER48.69%→49.88%, correct253→242, precision62.94%→59.75%. This small subgroup cannot establish a population effect, but it does not support claiming improved isolated names. Multiword names also exist, so this subgroup is not equivalent to all names. Full-cohort gains largely occur in multiword examples.

## Signer effects

| Signer | A native ΔCER pp | A phone ΔCER pp | B native ΔCER pp | B phone ΔCER pp |
|---|---:|---:|---:|---:|
| 001e | -8.58 | -7.30 | -2.16 | -4.76 |
| 1c15 | -1.77 | -1.33 | +0.45 | +2.27 |
| 28d4 | -5.12 | -8.84 | -4.39 | -6.34 |
| 2b19 | -4.80 | -1.75 | -4.57 | -2.74 |
| 4e6b | -1.33 | -4.44 | -7.48 | -4.21 |
| 5ce0 | -0.81 | +0.00 | -4.14 | +3.01 |
| 661f | +0.42 | -5.51 | -2.30 | -0.46 |
| a459 | +2.20 | -5.73 | -2.21 | -3.54 |
| aeed | +1.67 | -2.09 | -5.12 | -5.12 |
| c28d | -5.07 | -5.07 | -9.05 | -7.14 |
| c6e5 | -5.56 | -4.76 | -3.23 | -10.60 |
| d516 | -5.70 | -2.63 | -8.18 | -2.73 |
| d5fd | -4.85 | +1.76 | -3.04 | -4.35 |
| ebdb | +7.14 | -4.46 | -5.46 | -3.78 |
| f896 | -5.19 | -0.87 | -3.38 | -3.86 |

Native A improves11/15; native B14/15. Phone A13 improve/1 regress/1 tie; phone B13 improve/2 regress. Broad aggregate signer improvement is real, but does not mean every character or every sequence improved.

## J/Z/repeated-letter groups — full sequence CER

| Cohort/view/group | Sequences | epoch038 CER | V2 CER |
|---|---:|---:|---:|
| dev_a/native/J | 59 | 43.60% | 40.80% |
| dev_a/native/Z | 52 | 43.31% | 42.07% |
| dev_a/native/REPEATED_LETTERS | 109 | 43.17% | 40.25% |
| dev_a/phone/J | 59 | 48.53% | 45.47% |
| dev_a/phone/Z | 52 | 49.52% | 44.00% |
| dev_a/phone/REPEATED_LETTERS | 109 | 47.35% | 44.16% |
| dev_b/native/J | 61 | 42.66% | 39.55% |
| dev_b/native/Z | 25 | 38.86% | 28.86% |
| dev_b/native/REPEATED_LETTERS | 110 | 45.48% | 41.34% |
| dev_b/phone/J | 61 | 47.14% | 42.91% |
| dev_b/phone/Z | 25 | 41.71% | 35.14% |
| dev_b/phone/REPEATED_LETTERS | 110 | 49.90% | 46.10% |

Lower J/Z-containing sequence CER is not proof of recognizing J/Z better. Phone J recall A35/62→31/62, B34/65→36/65; Z A22/58→20/58, B10/26→9/26. Repeated-letter phone groups still have zero exact strings in both models/cohorts.

## Synthetic missing-evidence stress

| Cohort/stress | epoch038 CER | V2 CER | Correct chars | S/D/I epoch038 → V2 | Precision | Extra CER above own normal phone: old → V2 pp |
|---|---:|---:|---:|---|---:|---:|
| dev_a/stress_moderate | 52.16% | 48.94% | 1781 → 1905 | 800/876/127 → 843/709/140 | 65.77% → 65.96% | 5.18 → 5.47 |
| dev_a/stress_heavy | 59.97% | 55.34% | 1440 → 1628 | 813/1204/56 → 936/893/84 | 62.36% → 61.48% | 12.99 → 11.86 |
| dev_a/stress_contiguous | 53.66% | 48.37% | 1722 → 1909 | 830/905/120 → 843/705/124 | 64.45% → 66.38% | 6.68 → 4.89 |
| dev_b/stress_moderate | 52.40% | 48.31% | 1716 → 1854 | 782/876/110 → 805/715/110 | 65.80% → 66.96% | 6.16 → 5.60 |
| dev_b/stress_heavy | 59.28% | 54.83% | 1415 → 1607 | 769/1190/41 → 874/893/83 | 63.60% → 62.68% | 13.04 → 12.12 |
| dev_b/stress_contiguous | 52.87% | 48.78% | 1689 → 1829 | 792/893/99 → 806/739/101 | 65.47% → 66.85% | 6.64 → 6.08 |

All six absolute stress CERs improve, predominantly through fewer deletions. Substitutions rise in all six; heavy-stress precision worsens in both cohorts. Relative degradation modestly improves in five of six comparisons; DEV-A moderate is slightly worse. Missing-evidence robustness is partially improved, not solved.1536 stress-lineage records retain timestep count/Adapter identity and obey withdrawal budgets. The same inputs are used for both models. These are synthetic evidence withdrawal, not measured CameraX simulation.

## Per-character recall — phone, original edit alignment

| Character | A old → V2 correct/reference | B old → V2 correct/reference |
|---|---|---|
| A | 290 → 285 /375 | 300 → 292 /385 |
| B | 40 → 45 /68 | 38 → 37 /60 |
| C | 66 → 57 /116 | 69 → 64 /117 |
| D | 35 → 39 /100 | 38 → 40 /94 |
| E | 201 → 208 /335 | 203 → 213 /335 |
| F | 17 → 18 /27 | 14 → 16 /35 |
| G | 23 → 23 /60 | 37 → 43 /79 |
| H | 52 → 69 /84 | 73 → 76 /96 |
| I | 155 → 160 /205 | 159 → 161 /219 |
| J | 35 → 31 /62 | 34 → 36 /65 |
| K | 33 → 32 /53 | 15 → 21 /43 |
| L | 92 → 80 /202 | 93 → 85 /203 |
| M | 40 → 54 /84 | 44 → 48 /87 |
| N | 183 → 192 /302 | 197 → 193 /276 |
| O | 133 → 152 /216 | 128 → 133 /209 |
| P | 23 → 24 /50 | 15 → 16 /41 |
| Q | 3 → 2 /11 | 0 → 1 /6 |
| R | 140 → 139 /231 | 140 → 165 /250 |
| S | 111 → 75 /160 | 124 → 75 /180 |
| T | 101 → 110 /155 | 65 → 79 /127 |
| U | 21 → 33 /83 | 17 → 25 /61 |
| V | 11 → 13 /42 | 11 → 10 /33 |
| W | 23 → 24 /44 | 16 → 21 /33 |
| X | 3 → 2 /10 | 3 → 1 /9 |
| Y | 26 → 32 /62 | 15 → 21 /52 |
| Z | 22 → 20 /58 | 10 → 9 /26 |
| SPACE | 121 → 180 /262 | 111 → 178 /253 |

## Representative paired phone predictions

| Cohort | Reference | epoch038 | V2 | Error delta |
|---|---|---|---|---:|
| dev_a | `BRIDGEPORT CONNECTICUT` | `BI PRTCONECTICERTS` | `BAIDGEPORT CONECTICERT` | -6 |
| dev_a | `FRANCIS ARROYO` | `FDANCASAOI O` | `FANCIS AROYO` | -5 |
| dev_a | `DONNA BOOTH` | `N BOAH` | `DONA BOTH` | -4 |
| dev_a | `WEST COVINA CALIFORNIA` | `WETCOVINA CALIENRNIA` | `WMTCOVIN CLIEUNIA` | +4 |
| dev_a | `CLINICALSUPPLYCOMPANY` | `JRINI A SRAIY OMOMPANIY` | `RNIA ER TI OMOMPNIY` | +3 |
| dev_a | `GUBO` | `GRBO` | `EHU WBO` | +3 |
| dev_b | `MARJORIE CHARLES` | `OSRIJ JORUIOE OHANRLES` | `MOSRI ORIE CHARLES` | -5 |
| dev_b | `ANAHEIM CALIFORNIA` | `AN OI JCOLIFORNIAY` | `ANHEIM COLIFORNIA` | -5 |
| dev_b | `JEANNIE GONZALES` | `OSNMIOGONTSLES` | `JEANMI GONTALEA` | -4 |
| dev_b | `DOMINGO CHRISTENSEN` | `DOMN E HCSTN EN` | `MADONH HIATNTENT` | +4 |
| dev_b | `ALANNA HUMPHREY` | `ANA HUMHEAS` | `TNA  HUE GHEAS` | +4 |
| dev_b | `ARTISTES` | `ARTNISTES` | `ARTNIN TE` | +3 |

Full sample IDs and all scores, signer deltas, confusion counts and examples are in the machine-readable analysis.

## What is known, supported, and uncertain

**Known:** exact saved-evaluation gain under frozen decoder; broad signer-level effect; better phone precision and lower edit totals; SPACE-dominated correct-count improvement; S and some other letter regressions; inconsistent single-word performance; very low exact-string counts.

**Supported interpretation:** full-sequence context/training package improves phrase decoding and reduces some missing-evidence deletions. Improvement extends beyond SPACE, but fine letter discrimination remains the main unresolved quality limitation. No implementation correctness failure was demonstrated.

**Uncertain:** individual contribution of noncausality versus stronger masking/robustness/scratch initialization/LR; linguistic frame-level cause of S loss; live-phone quality; trained V2 export/Android numerical parity and Xiaomi runtime. Smoke-model export feasibility does not establish trained epoch046 parity.

DEV-A has been used repeatedly for selection. DEV-B shares its15 signers and has been opened before; this is post-lock confirmation, not independent population testing. Posthoc single-word/SPACE diagnostics are transparent cautionary checks, not retrospectively changed selection thresholds. No statistical significance or production-accuracy claim is made.

## Preservation, artifacts and repeatability

-1594 protected file hashes checked against the architecture-gate inventory: zero changes. WORD, Candidate01, Adapter.v1, Android/Context Assist and reference packages were not edited. No fresh device regression claimed because no device work occurred.
- Only new audit script/analysis/report and append-only operational handoff records were created.
- Source report: `runs/fingerspelling_sequence_v2_01/final_evaluation.json`.
- Independent evidence: `artifacts/fingerspelling_sequence_v2_review_01/analysis.json`.
- Repeat review: `& .\.venv\Scripts\python.exe -m artifacts.fingerspelling_sequence_v2_review_01.review_saved_results` from `F:\ASL DATASET\5. Apphear3`. It reads saved results/manifests/protected files only.

**V2_RETAIN_RESEARCH_CANDIDATE_HOLD_DEFAULT_PROMOTION**
