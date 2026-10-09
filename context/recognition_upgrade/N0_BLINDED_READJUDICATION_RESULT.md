# N0 Blinded Re-adjudication Result

**Date:** 2026-08-21  
**Formal decision:** `N0_BLINDED_READJUDICATION_COMPLETE_DIVERSITY_INSUFFICIENT`  
**Scope:** human semantic adjudication and benchmark governance only

## Result

The N0 review succeeded as a human-adjudication exercise. It did not supply enough independent images to finish `NEGATIVE_GOLD_V1`.

| Measure | Result |
|---|---:|
| Review rows completed | 275 / 275 |
| Canonical images | 250 |
| Hidden repeat rows | 25 |
| Exact repeat agreements | 25 / 25 (100%) |
| Critical `ZERO_HAND`/non-`ZERO_HAND` disagreements | 0 |
| Canonical `ZERO_HAND` | 238 |
| Canonical `VISIBLE_IDLE_HAND` | 9 |
| Canonical `TRANSITION` | 3 |
| `ZERO_HAND` surviving frozen diversity rules | 43 |
| Redundant `ZERO_HAND` retained outside the benchmark | 195 |

The semantic label set is therefore accepted. `Finalize` correctly returned an insufficient-diversity stop because only 43 new zeros survived, not because review quality failed. The 195 redundant zeros are preserved for non-independent diagnostics but cannot count toward the benchmark denominator.

## Frozen rules

- Exact duplicates are removed by SHA-256.
- Near duplicates are removed when 64-bit dHash Hamming distance is `<=4`.
- Candidate comparison order and per-clip selection follow the frozen N0 protocol/config.
- Hidden repeats never count as independent evidence.
- No threshold was changed after review.

The retained 43 cover 31 clips, six participants, five devices, and five environments. The finalizer's fourth-frame-per-clip fallback was invoked, but could not overcome image redundancy.

## Preserved evidence and hashes

Canonical package: `artifacts/recognition_upgrade/perception_backend_replacement/n0_blinded_readjudication_01`

| Evidence | SHA-256 |
|---|---|
| Reviewed queue containing all canonical labels and hidden-repeat mapping | `D489404BFE829281161373FA9DA8D34C7B89BDCBADB66347FD556AAED1A5DD87` |
| Repeat-QC result | `70F8C289EA41A8325A031097107665A852D8628389091CA67A3A4AF30CDA63D9` |
| Formal finalizer result | `0D61537C55C16A3C88AA7098FCE06A903671A9B9115FE0581FA3B6B008E42504` |
| Canonical 250-row export | `DFBF5573EC8474D4EE0769B39B776A97B1B9456764F444F12BA37CA52716FEE4` |
| Diversity-clean 43-row export | `63473834B6D9E948CBB96EE748546B1D173EBC4A2053B8B6DD35ED6C979BE0FA` |
| Redundant 195-row export | `70AC9130C0A3EACB771EF5021F8464586BB1CB0846B2053F808E09CE45EF955D` |
| N0 config | `0DE1ED0F5CAF87AAF323D5E7336D271E1F65F9E59074EFA44D8F748855740D3D` |
| N0 protocol | `453DCB1C458C8AC9B25377F8A09D707F43E240B753403495ADD78507A66B23B1` |
| N0 runner | `C86C7117A3C15C9CD56D8E2E0751328175D24808F88BBDF2E187481E1B4F7898` |

## Consequence

The corrected-gold 33 and N0 43 form a valid 76-frame immutable seed. `NEGATIVE_GOLD_V1` remains incomplete at `76/200`, with a deficit of 124 independent human-verified `ZERO_HAND` frames. The next action is blinded review of diversity-screened existing RGB, not a model experiment and not new recording.

