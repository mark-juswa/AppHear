# NEGATIVE_GOLD_V1 external confirmation package

Date: 2026-08-22  
Status: `NEGATIVE_GOLD_EXTERNAL_CONFIRMATION_PACKAGE_FROZEN_UNREVIEWED`

## Executive result

The final bounded second-pass package is prepared and validated. It contains 160 canonical
Open Images candidates plus 20 concealed byte-identical repeats (180 review rows total).
No second-pass human labels exist yet, so no external image has been promoted and
NEGATIVE_GOLD_V1 remains 76/200.

The completed first-pass package was treated as immutable. Its recorded hashes all match.
The first-pass result contains 181 canonical provisional `ZERO_HAND` images. Two canonical
images participated in a binary hidden-repeat disagreement; only one was a provisional zero.
Excluding all discordant canonical images therefore leaves exactly 180 eligible provisional
zeros. The confirmation package selects 160 from that pool.

## Frozen selection

Selection used only Open Images source metadata, authorship/category metadata, and the
already-frozen exact/64-bit-dHash rules. It did not use MediaPipe, RTMDet, any other model,
confidence, or prediction output.

| Property | Frozen value |
|---|---:|
| Eligible non-discordant provisional zeros | 180 |
| Canonical confirmation candidates | 160 |
| Concealed repeats | 20 |
| Total review rows | 180 |
| Person-free discovery | 122 |
| People-present discovery | 38 |
| Scene buckets | 10 |
| Unique authors | 159 |
| Unique primary metadata labels | 134 |
| Minimum dHash distance within selected set | 10 |
| Minimum dHash distance from existing 76-frame seed | 10 |

Scene composition is: ANIMAL 19, ARCHITECTURE 15, CLOTHING 19, FOOD 15, INDOOR 15,
MIXED 20, NATURE 14, OBJECT 14, TRANSPORT 17, and URBAN 12. The frozen conflict rule remains
64-bit dHash Hamming distance `<=4`; it was not changed after reviewing any labels.

## Review blindness and QC

The visible queue contains only a neutral review ID, image path, review status, semantic
class, and optional note. The UI does not expose the first-pass label, Open Images metadata,
discovery category, QC history, model output, or repeat identity. It asks:

> Is ANY part of a human hand visible anywhere in this image?

The buttons are `ZERO_HAND`, `HAND_VISIBLE`, and `UNCERTAIN`. The UI supports full-image fit,
zoom, keyboard shortcuts, optional notes, atomic saving, and resume. Every concealed repeat
is an exact byte copy of its canonical image, is separated in the randomized queue, and is
frozen in the internal repeat map.

After review, the hard gate is zero `ZERO_HAND`/non-`ZERO_HAND` repeat disagreements; overall
three-class exact repeat agreement must also be at least 0.92. Promotion later requires
`FIRST_PASS=ZERO_HAND AND SECOND_PASS=ZERO_HAND`, followed by the unchanged exact/dHash checks.

## Provenance and package

- Branch: `codex/recognition-stable-ru-d10`
- HEAD at preparation: `7dd4fa05f2e7dffd3f06a2fdc88f90b1ea66836f`
- Protocol: `apphear.negative_gold.external_confirmation.v1`
- Selection seed: `20260827`
- Repeat-order seed: `20260828`
- Source/license manifest SHA-256: `80aee65f5444a2bc2b798279fd976579e86771b5970250fe77244da331e80165`
- Internal selection SHA-256: `e6cf35b5f640d00bde99f48d204b314146a62cc048db54520b30a7b2c52ad66c`
- Unreviewed queue SHA-256: `b526697adb91ee2e1adc8af66e45c1847e24d0c38ac6232d8b22a32cfb1ae9f2`
- Frozen repeat-map SHA-256: `68d35d40303d82955bf86938fed0bbf48be71434f26e4664edd1cd2e407fb5eb`

Package:
`artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_external_confirmation_01`

The package preserves a selected source/license manifest, complete attribution ledger,
source-artifact hash ledger, internal first-pass linkage, neutral queue, repeat map, frozen
source bytes, preparation summary, and provenance manifest. No new images were downloaded.

## Validation and next action

Ruff and Black pass. The focused confirmation and inherited Open Images tests pass 15/15.
Package status validation reports 180 rows, 160 canonical candidates, 20 repeats, zero
structural errors, and 0/180 completed, which is the expected pre-review state.

From PowerShell, launch the human review with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_negative_gold_external_confirmation.ps1" -Command Review
```

After all rows are labeled, run the same command with `-Command Check` and return the output.
Do not run any finalizer before the completed labels and repeat QC are processed.

