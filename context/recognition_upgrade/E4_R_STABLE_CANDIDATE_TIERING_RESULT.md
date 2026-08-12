# E4-R Stable-Candidate Tiering Result

**Purpose:** Record the completed E4-R tiering analysis for the dynamic mixed recognition roadmap.

**Scope:** Offline analysis only. No extraction, training, Android changes, model export, production asset replacement, or dataset mutation occurred.

**Current status:** COMPLETE / PASSED STRUCTURAL CHECK. Result authorizes E4-S package planning only, not Android or production use.

**Last updated:** 2026-07-31.

## Verified Project References

- Runner: `pipeline/rgb/e4_r_stable_candidate_tiering.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_r_stable_candidate_tiering_01`
- Tier table: `artifacts/recognition_upgrade/e4_generalization/e4_r_stable_candidate_tiering_01/tiered_candidates.csv`
- Summary: `artifacts/recognition_upgrade/e4_generalization/e4_r_stable_candidate_tiering_01/tiering_summary.json`
- Report: `artifacts/recognition_upgrade/e4_generalization/e4_r_stable_candidate_tiering_01/tiering_report.md`
- Check report: `artifacts/recognition_upgrade/e4_generalization/e4_r_stable_candidate_tiering_01/check_report.json`

## Inputs

E4-R ranked the 236-label inventory using existing evidence only:

- E4-M dual-source candidate screen
- E4-N 5-sign passed training screen
- E4-O GET/WELCOME2 failed expansion screen
- E4-P 20-sign failed pressure test
- E4-Q failed `GOOD/SORRY/HELP/BECOME` confusion resolver

## Result Summary

Rows ranked: `236`.

Tier counts:

| Tier | Count | Meaning |
|---|---:|---|
| `A_primary_ready_guarded` | `4` | Eligible for next stable-primary landmark experiment, not production release |
| `B_confusion_specialist_or_repair` | `12` | Known hard/confusing/rejected signs requiring specialist, data repair, or defer |
| `B_borderline_review` | `6` | Looked borderline in failed E4-P pressure run; cannot enter primary directly |
| `C_defer_more_evidence` | `9` | Needs validation, extraction, or more support |
| `D_inventory_only` | `205` | Mostly ASL Citizen-only or not part of current dual-source path |

## Primary-Ready Guarded Signs

These are eligible for E4-S stable-primary landmark training:

- `GOOD`
- `HELLO`
- `HAVE`
- `KNOW`

Important: this means eligible for the next experiment only. It does not mean Android production-ready. These signs still need calibration, no-sign/OOV, quantization, and device gates before release.

## Confusion / Repair Signs

E4-R keeps these out of the stable primary path:

- `BECOME`
- `BYE`
- `CLEAN`
- `GET`
- `HELP`
- `MAKE`
- `NICE`
- `NO`
- `SORRY`
- `START`
- `WHAT1`
- `YES`

Reason categories:

- `SORRY/BECOME/HELP`: active confusion group; E4-P/E4-Q show landmark-only confusion remains unresolved.
- `MAKE/GET`: known collapse with `GOOD` from E4-L/E4-O.
- `BYE/NO/YES`: prior local separability failures from E4-G/E4-H.
- `THANKYOU`: already tracked as label/variant cleanup, but not present in the top E4-R hard table because it was not part of E4-P pressure labels.
- `CLEAN/NICE/START/WHAT1`: weak in E4-P pressure test.

## Borderline Review Signs

These signs had some positive E4-P signal but cannot be admitted directly because E4-P failed overall:

- `CLOSE`
- `GIVE`
- `MEET`
- `STAND2`
- `WANT2`
- `WASH2`

They require a dedicated stable-primary batch gate or more review before primary inclusion.

## Decision

Proceed next to **E4-S stable-primary landmark package design** using the guarded Tier-A signs first:

`GOOD`, `HELLO`, `HAVE`, `KNOW`

Do not jump directly to Android, broad RGB/hybrid, or specialist resolvers. The primary path and router simulation need a clean stable baseline first.

## Engineering Interpretation

E4-R confirms the dynamic mixed strategy:

- There is a small stable landmark-primary vocabulary candidate.
- Most available signs are not ready for direct primary inclusion.
- The next useful work is not another random expansion; it is a controlled stable-primary package and then router simulation.
- Specialist visual/hybrid work should target registered hard groups after the primary path is clean.

## Assumptions

- E4-N's passed result is still valid evidence for `HAVE` and `KNOW`.
- E4-P's failed result can identify warnings and borderline signs, but cannot promote signs by itself.
- E4-Q's no-go result is decisive enough to keep `SORRY/BECOME/HELP` out of primary-only promotion for now.

## Risks

- The primary-ready set is small compared with product goals.
- `GOOD` has known collapse interactions with `MAKE/GET`, so future expansions must monitor it.
- `SORRY` was previously strong in small local-core runs but failed in broader pressure/resolver contexts; treating it as stable would be unsafe.
- Borderline E4-P signs may be useful, but adding them now would mix stable and uncertain evidence.

## Next Required Action

Prepare E4-S as a controlled stable-primary landmark training package. E4-S should use the Tier-A guarded signs and should include calibration/no-sign planning before any Android work.
