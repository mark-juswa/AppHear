# NEGATIVE_GOLD_V1 item-level contamination audit protocol

Status: frozen before audit selection and human review.

## Historical boundary

The first Open Images review remains `QC FAIL`. The second confirmation review remains
`NEGATIVE_GOLD_V1_STILL_INCOMPLETE` under its original run-level QC rule. This protocol does not
rewrite either result. It introduces a new item-level decision boundary because two human repeat
inconsistencies invalidated an otherwise dual-confirmed batch.

## Eligible pool

1. Start with the 160 candidates mechanically labeled `ZERO_HAND` in both completed passes.
2. Permanently exclude every canonical item involved in a second-pass binary
   `ZERO_HAND`/non-`ZERO_HAND` repeat disagreement.
3. Preserve those conflicts and all original labels/hashes without repair.
4. Verify the expected retained pool of 158, source bytes, first/second-pass provenance, frozen
   exact/dHash rule, and no overlap with the trusted 76-frame seed.

## Frozen initial audit sampling

- Sample size: 40 canonical images.
- Random seed: `20260822`.
- Model output is prohibited.
- Sampling uses only Open Images ID plus hidden discovery category and scene bucket.
- The retained pool has 19 nonempty `(discovery_category, scene_bucket)` strata. Pure random
  sampling could omit the rare one- and two-item strata, so stratification is preregistered.
- Assign one draw to every nonempty stratum. Allocate the remaining 21 draws proportionally to
  each stratum's remaining capacity using largest remainders; ties use lexical stratum order.
- Within each stratum, sort by Open Images ID and shuffle with a deterministic seed derived from
  `20260822` and the stratum name. Randomly shuffle the combined 40-row presentation order using
  seed `20260823`.
- No concealed repeats are added. This protocol estimates item contamination and does not use a
  new run-level repeat-consistency gate.

The reviewer sees only a neutral review ID, the image, progress, optional notes, the frozen
question, and the three labels. Prior labels, metadata, categories, model output, and historical
repeat status remain hidden.

## Preregistered decisions

- Initial 40 has 0 clear `HUMAN_HAND_VISIBLE` cases and no tooling/provenance defect: proceed to
  diversity selection. Audited `UNCERTAIN` rows are excluded but do not count as contamination.
- Initial 40 has exactly 1 clear contamination: exclude it and prepare one bounded 20-image
  follow-up from previously unaudited eligible candidates. Follow-up 0 contamination proceeds;
  follow-up >=1 stops.
- Initial 40 has >=2 clear contaminations, or the follow-up fails: `POOL_REJECTED`.
- If audit passes, exclude conflicts, audit contamination/uncertain rows, duplicates under the
  unchanged dHash `<=4` rule, and seed overlap. Diversity-rank the remainder, select exactly 124,
  freeze NEGATIVE_GOLD_V1 at 200, and place surplus in NEGATIVE_GOLD_RESERVE.
- Do not start a follow-up or freeze manifests automatically before the human result is processed.

No detector, model, training, download, Android test, or S4-S7 change is permitted.

