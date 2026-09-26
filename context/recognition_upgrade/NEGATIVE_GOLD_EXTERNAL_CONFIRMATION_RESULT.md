# NEGATIVE_GOLD_V1 external confirmation result

Date: 2026-08-22  
Decision: `NEGATIVE_GOLD_V1_STILL_INCOMPLETE`

## Executive conclusion

The second-pass review is structurally complete, but its preregistered human-consistency gate
failed. All 160 canonical candidates were labeled `ZERO_HAND` in the second pass. However, two
of the 20 concealed byte-identical repeats received a non-`ZERO_HAND` label when shown again.
Exact three-class and binary zero/non-zero agreement were both 18/20 = 90%, below the required
92% exact threshold and, more importantly, above the allowed zero critical binary disagreements.

The canonical decisions were not silently repaired. No external frame was promoted.
NEGATIVE_GOLD_V1 remains 76/200, with an exact trusted deficit of 124.

## Completed review

| Measure | Result |
|---|---:|
| Total review rows | 180/180 |
| Canonical candidates | 160 |
| Concealed repeats | 20 |
| Canonical `ZERO_HAND` | 160 |
| Canonical `HAND_VISIBLE` | 0 |
| Canonical `UNCERTAIN` | 0 |
| Structural errors | 0 |

The user-facing `Check` result counted repeats and therefore reported 178 `ZERO_HAND`, one
`HAND_VISIBLE`, and one `UNCERTAIN`. Removing the 20 repeats leaves all 160 canonical rows labeled
`ZERO_HAND`.

## Hidden-repeat QC

| Gate | Required | Result | Pass? |
|---|---:|---:|---|
| Exact three-class agreement | >=92% | 18/20 = 90% | NO |
| Binary `ZERO_HAND`/non-`ZERO_HAND` agreement | 20/20 | 18/20 = 90% | NO |
| Critical binary disagreements | 0 | 2 | NO |
| Repeat source bytes identical | all | 20/20 | YES |

Discordant byte-identical pairs:

1. `confirmation_0098=ZERO_HAND` versus `confirmation_0032=HAND_VISIBLE`, source SHA-256
   `0a54326a853b0f1739de354234439075ae6993e39e3a669f2d4f71498414c39a`.
2. `confirmation_0097=ZERO_HAND` versus `confirmation_0034=UNCERTAIN`, source SHA-256
   `aca8d0b6a7aec6e39575a034c45993de5be07d617ae6c321141fac7e970b01b5`.

A diagnostic visual inspection explains why the gate is meaningful but does not override the
saved labels. The first image clearly contains a speaker's visible human hands. The second shows
garden-gnome figures with sculpted hands; no human hand is apparent, but the object is plausibly
confusing under a rapid review. This evidence confirms human semantic inconsistency rather than a
repeat-copy or mapping defect.

## Dual-pass and diversity diagnostics

All 160 selected candidates had a first-pass `ZERO_HAND` label and a canonical second-pass
`ZERO_HAND` label, so the mechanical dual-pass count is 160. All 160 remain exact/dHash clean
against each other and the existing 76-frame seed; minimum internal and seed-relative dHash
distance is 10 against the frozen conflict boundary `<=4`.

These are diagnostics only. The run-level repeat-QC failure invalidates promotion of the whole
confirmation pass. Therefore:

- `DUAL_CONFIRMED_ZERO_HAND_DIAGNOSTIC = 160`
- `DIVERSITY_CLEAN_CONFIRMED_DIAGNOSTIC = 160`
- `CONFIRMED_NEW_ZERO_HAND = 0`
- selected benchmark additions = 0
- reserve = 0
- final trusted total = 76
- exact remaining deficit = 124

No `NEGATIVE_GOLD_V1` or `NEGATIVE_GOLD_RESERVE` manifest was created.

## Artifacts and provenance

Formal outputs are under:
`artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_external_confirmation_01/finalization`

They include:

- `negative_gold_external_confirmation_result.json`
- `second_pass_canonical_labels.csv`
- `hidden_repeat_qc.csv` and `.json`
- `dual_pass_comparison.csv`
- `final_diversity_dedup_report.json`
- `provenance_hash_manifest.json`

The first-pass hashes still match the frozen configuration. The repeat map and exact source bytes
match. No human label was overridden. No perception model, training, download, Android, or S4-S7
work occurred.

## Evaluation and next action

The correct decision is `NEGATIVE_GOLD_V1_STILL_INCOMPLETE`, not a benchmark freeze. The review
success flag means all rows were saved and structurally valid; it does not mean repeat QC passed.

Stop here. Do not automatically create another broad review loop. If the user separately approves
a repair, the smallest defensible action is an independently blinded adjudication of only the two
discordant source images, with their current labels and repeat identities hidden. Until such a
protocol is approved and passed, the trusted benchmark remains 76/200.

