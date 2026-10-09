# NEGATIVE_GOLD_V1 External Open Images Review Result

**Date:** 2026-08-21  
**Decision:** `OPEN_IMAGES_REVIEW_COMPLETE_QC_FAILED_REPAIR_REQUIRED`  
**Scope:** human-review processing and benchmark governance only

## Executive conclusion

All 240 rows were completed and structurally valid, but the hard concealed-repeat gate failed. Therefore none of the 181 provisional canonical `ZERO_HAND` labels has been promoted into `NEGATIVE_GOLD_V1`.

```text
TRUSTED_NEGATIVE_GOLD_BEFORE = 76
TRUSTED_NEGATIVE_GOLD_AFTER = 76
REMAINING_TRUSTED_DEFICIT = 124
BENCHMARK_FROZEN = false
```

The completed review contains ample likely zero-hand material. The blocker is label confirmation, not image supply or diversity.

## Canonical result

The user-facing count included 20 hidden repeats. Removing them gives:

| Human label | Canonical rows |
|---|---:|
| `ZERO_HAND` | 181 |
| `HAND_VISIBLE` | 38 |
| `UNCERTAIN` | 1 |
| **Total** | **220** |

The 181 zero labels are provisional because hard QC failed. Excluding canonical images involved in any zero/non-zero repeat disagreement leaves 180 provisional zeros, still not trusted benchmark entries.

## Concealed-repeat QC

| Measure | Result |
|---|---:|
| Exact image pairs | 20/20 byte-identical |
| Exact three-class agreements | 18/20 |
| Overall three-class agreement | 90.0% |
| Three-class disagreements | 2 |
| `ZERO_HAND` vs non-zero disagreements | 2 |
| Critical `ZERO_HAND` vs `HAND_VISIBLE` disagreements | **1** |
| Hard QC | **FAIL** |

Discordant pairs:

| Canonical row | Canonical label | Repeat row | Repeat label | Interpretation |
|---|---|---|---|---|
| `external_0177` | `ZERO_HAND` | `external_0012` | `UNCERTAIN` | Zero/non-zero inconsistency; canonical zero is ineligible. |
| `external_0216` | `HAND_VISIBLE` | `external_0113` | `ZERO_HAND` | Critical hard-gate disagreement. |

SHA-256 confirms that each pair contains exactly the same source bytes. The repeat map and copies are correct.

Visual verification found visible human hands in both discordant images: a crowded group scene contains several hands, and the child image clearly shows both hands. This visual check diagnoses the disagreement but does not replace the human labels or silently relabel the rows.

## Discovery-category result

| Metadata discovery category | Canonical rows | `ZERO_HAND` | `HAND_VISIBLE` | `UNCERTAIN` |
|---|---:|---:|---:|---:|
| Person-free discovery | 143 | 142 | 1 | 0 |
| People-present discovery | 77 | 39 | 37 | 1 |

The person-free metadata category's one visible-hand result directly confirms the protocol warning: Open Images annotation metadata is useful for discovery but is not zero-hand ground truth.

The 181 provisional zeros remain diverse across all ten frozen scene buckets: Animal 21, Architecture 17, Clothing 20, Food 17, Indoor 17, Mixed 23, Nature 16, Object 16, Transport 20, and Urban 14.

## Preserved evidence

Package: `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_open_images_v7_01`

| Artifact | SHA-256 |
|---|---|
| Completed review queue | `D2482994AC708400F8598880E3669C5E22AA7D855AD488B32966E90E22A5801A` |
| Canonical 220 labels | `6A80E81AFFCF3DFE162CF6EF9EBF6DE81AF99BB6CA04852CB50A31499AF6AA2B` |
| Hidden-repeat QC CSV | `0FBD4827A789AF81FEEBA3198005E3EC67E8E178D8EE84593F2E460AE72392FE` |
| Hidden-repeat QC JSON | `D3D544B39C0F7666C3B8B14635A5E66D2AE53504F286289243FA9AF6E5447FE1` |
| Formal finalizer result | `E71CB9D360FB42D786DD7CC0C9711159213730F0E7A29A633388B43145CEB37D` |

No final 200-row manifest or reserve was created because that would falsely imply that the hard gate passed.

## Recommended repair

Do not repeat external downloading and do not use a model. Existing RGB is sufficient.

The scientifically conservative next action is a second blinded confirmation pass over a diversity-maximized subset of the provisional zeros, excluding both discordant images. A reasonable bounded package is 150 canonical candidates plus 15 concealed repeats:

- select from the 180 non-discordant provisional zeros;
- hide first-pass labels and all source metadata;
- use the same `ZERO_HAND` / `HAND_VISIBLE` / `UNCERTAIN` question;
- require zero critical repeat disagreement;
- accept only images labeled `ZERO_HAND` in both passes;
- require at least 124 dual-confirmed, frozen-rule-independent images;
- then select exactly the best 124 and freeze any additional confirmed images as reserve.

This provides 26 rows of attrition allowance while avoiding another full 220-image review. A two-image tiebreak alone is not sufficient because it would not repair the preregistered run-level hidden-repeat failure.

No detector, classifier, perception model, training, fine-tuning, Android, S4, S5, S6, or S7 work occurred.

