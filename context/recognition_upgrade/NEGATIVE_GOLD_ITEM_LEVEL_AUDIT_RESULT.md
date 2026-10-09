# NEGATIVE_GOLD_V1 Item-Level Audit Result

Decision: `NEGATIVE_GOLD_V1_COMPLETE`

NEGATIVE_GOLD_V1 is complete and frozen at 200 trusted, diverse zero-actual-human-hand images.
The benchmark-construction phase is closed.

## Historical boundary

This protocol does not rewrite the earlier outcomes:

- First Open Images review: `QC FAIL`.
- Second confirmation review: `QC FAIL`; historical decision
  `NEGATIVE_GOLD_V1_STILL_INCOMPLETE`.

The new protocol introduced item-level exclusions and a bounded random pool audit because the
old run-level all-or-nothing rule discarded substantial dual-confirmed evidence after two human
repeat inconsistencies. This is a benchmark-governance correction, not a lowered model gate.

## Conflict exclusions and retained pool

Two canonical candidates involved in second-pass binary repeat conflicts remain permanently
ineligible. Their labels and evidence were preserved without repair:

| Open Images ID | Pass 1 | Pass 2 canonical | Repeat | Status |
|---|---|---|---|---|
| `73df255e2dd09114` | ZERO_HAND | ZERO_HAND | HAND_VISIBLE | Permanently excluded |
| `6dbcd715a2aae68c` | ZERO_HAND | ZERO_HAND | UNCERTAIN | Permanently excluded |

- Dual-confirmed candidates before conflict exclusions: 160.
- Known-conflict exclusions: 2.
- Eligible retained pool: 158.

## Independent item-level audit

- Frozen sample: 40 images, selected with seed `20260822` and presented with seed `20260823`.
- Representation: all 19 scene/category strata; 12 people-present discovery candidates,
  28 person-free discovery candidates, and 40 unique authors.
- Result: 40 `NO_HUMAN_HAND_VISIBLE`, 0 `HUMAN_HAND_VISIBLE`, 0 `UNCERTAIN`.
- Clear actual-human-hand contamination: 0/40.
- Tooling/provenance defects: 0.
- Follow-up audit required: no.
- Preregistered branch: zero contamination permits benchmark selection.

The audit definition counted only real human hands. Statue, toy, mannequin, drawing, painting,
cartoon, figurine, sculpted, artificial, and photograph-inside-scene hands did not count unless a
real human hand was also visible.

## Final diversity selection

The full retained pool remained diversity-clean under the unchanged rule that a 64-bit dHash
Hamming distance `<=4` is a conflict.

- Diversity-clean eligible candidates: 158.
- Selected additions: 124.
- Reserve: 34.
- Existing trusted rows: 76.
- Final benchmark: 76 + 124 = 200.
- Remaining deficit: 0.
- Selected composition: 31 people-present and 93 person-free discovery candidates.
- Selected authors: 124 unique authors.
- Selected scene counts: animal 16, architecture 12, clothing 15, food 12, indoor 11,
  mixed 15, nature 10, object 11, transport 13, urban 9.
- Full-pool minimum internal/seed dHash distance: 10/10.
- Selected-set minimum internal/seed dHash distance: 16/16.

Selection used proportional quotas across all 19 strata, then deterministic farthest-first dHash
ranking against the trusted seed and earlier selections. Ties preferred lower quota fill, lower
author reuse, then Open Images ID. Of the 124 selected additions, 31 were themselves in the
40-image audit and 93 qualify through dual confirmation plus the passing random pool audit. The
manifest records this distinction explicitly.

## Frozen artifacts

- `finalization/NEGATIVE_GOLD_V1_MANIFEST.csv` and `.json`: frozen 200-row benchmark.
- `finalization/NEGATIVE_GOLD_RESERVE_MANIFEST.csv` and `.json`: 34-row reserve.
- `finalization/audit_labels.csv`: saved 40-image audit truth.
- `finalization/contamination_summary.json`: item-level decision evidence.
- `finalization/diversity_selection_report.json`: quotas, rankings, and diversity diagnostics.
- `finalization/negative_gold_item_level_audit_result.json`: machine-readable decision.
- `finalization/final_provenance_hash_manifest.json`: frozen source/result hashes.
- `known_conflict_exclusions.csv` and `.json`: preserved excluded-item evidence.

Independent verification passed:

- 200 manifest rows and 200 unique IDs/SHA-256 values;
- 76 existing plus 124 Open Images rows;
- 34 unique reserve rows, disjoint from the main benchmark;
- every main image path exists and every SHA-256 matches;
- no main-pool dHash pair violates the frozen threshold;
- focused tests: 3 passed;
- PowerShell runner parses successfully.

No detector, perception model, training, fine-tuning, download, Android test, or S4/S5/S6/S7
work occurred. The next perception phase was not started.

## Stopping point

Stop. NEGATIVE_GOLD_V1 construction is closed. Do not create another negative-data round or begin
the next perception experiment automatically. Reopen this benchmark only if a concrete benchmark
defect is later demonstrated.
