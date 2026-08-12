# E4-M Dual-Source Candidate Screening Preflight Result

**Purpose:** Record the first source-aware candidate inventory/ranking step after E4-L showed one-word expansion is too slow and unsafe.

**Scope:** Offline inventory and ranking only. No feature extraction, training, Android integration, model export, production recognizer replacement, source-video mutation, or dataset relabeling is authorized by this result.

**Current status:** Complete; preflight passed; follow-up bounded training package still requires approval.

**Last updated:** 2026-07-31.

## Verified Project References

- Runner: `pipeline/rgb/e4_m_dual_source_screen.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01`
- Summary JSON: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01/reports/screen_summary.json`
- Summary Markdown: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01/reports/screen_summary.md`
- Ranked inventory: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01/tables/candidate_inventory_ranked.csv`
- Existing-feature candidates: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01/tables/train_ready_existing_features.csv`
- Extraction-needed candidates: `artifacts/recognition_upgrade/e4_generalization/e4_m_dual_source_candidate_screen_01/tables/needs_local_feature_extraction.csv`
- ASL Citizen feature source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_conversational`
- Existing local feature source: `F:\ASL DATASET\ASL CITIZEN\derived\apphear3\features_streaming_recorded_local_pc_236\recorded.npz`
- Local audit source: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_audit_01`
- Local validation source: `artifacts/recognition_upgrade/e4_generalization/e4_c_local_supplementary_validation_01`

## What The Preflight Did

E4-M inspected the 236-class ASL Citizen conversational feature set and the existing local supplementary feature tensor, then joined that evidence with the local raw/validated clip inventories. It produced candidate recommendations using source-aware support thresholds, not accuracy claims.

The preflight explicitly preserves prior E4 evidence:

- `GOOD`, `HELLO`, and `SORRY` remain core controls.
- `MAKE` remains rejected because E4-L failed held-out signer testing.
- `BYE`, `NO`, `YES`, and `THANKYOU` are marked as prior-unstable/review-needed, not promoted by row counts alone.

## Result Summary

- Vocab size inspected: `236`
- Check result: passed with no errors
- Recommendation counts:
  - `asl_only_candidate_not_dual_source`: `215`
  - `keep_core_control`: `3`
  - `local_only_or_asl_support_weak`: `3`
  - `needs_local_feature_extraction`: `2`
  - `needs_prior_failure_review`: `3`
  - `needs_video_validation_first`: `6`
  - `reject_insufficient_support`: `1`
  - `reject_prior_failed_e4_l`: `1`
  - `train_ready_existing_features`: `2`

## Candidate Queue

### Existing-Feature Training Candidates

These are the only signs currently eligible for a cheap follow-up training screen without another local feature-extraction run:

| Gloss | ASL train/test | Existing local features | Validated local support | Status |
|---|---:|---:|---:|---|
| `HAVE` | `14/10` | `15` clips, `2` signers | `50` clips, `2` signers | train-ready diagnostic |
| `KNOW` | `10/13` | `11` clips, `2` signers | `50` clips, `2` signers | train-ready diagnostic |

### Promising But Needs Local Feature Extraction

| Gloss | ASL train/test | Existing local features | Validated local support | Status |
|---|---:|---:|---:|---|
| `GET` | `12/12` | `7` clips, `2` signers | `70` clips, `2` signers | extract before training |
| `WELCOME2` | `13/12` | `2` clips, `2` signers | `70` clips, `2` signers | extract before training |

### Prior-Unstable / Review Required

`BYE`, `NO`, and `YES` have enough visible support to appear attractive by counts, but earlier E4 experiments showed held-out instability. They must not be promoted by this preflight. They require explicit failure review, relabel/split/deferral, or a separate controlled intervention.

## Interpretation

This is not an accuracy result. It is a queue-building result.

The useful finding is that the immediately trainable dual-source pool is much smaller than the raw local inventory suggests. Most of the 236-class ASL Citizen vocabulary does not currently have enough local supplementary support to test source transfer honestly. The next high-value action is therefore a small bounded training screen for `HAVE` and `KNOW`, while deciding whether to extract `GET` and `WELCOME2` local features as the next expansion batch.

## Decisions

- Do not return to one-word manual expansion.
- Do not blindly merge ASL Citizen and local data.
- Do not promote `MAKE`, `BYE`, `NO`, `YES`, or `THANKYOU` from this preflight.
- Proceed next with a bounded dual-source training-screen package only if the user approves it.
- The first training screen should use `GOOD`/`HELLO`/`SORRY` as controls plus `HAVE` and `KNOW` as the first train-ready candidate batch.

## Risks

- `HAVE` and `KNOW` still have only two local feature signers, so even the next training screen is diagnostic, not production evidence.
- Existing local feature coverage is sparse compared with raw local videos.
- Label/variant compatibility is not proven by inventory counts.
- Source/provenance shortcuts remain possible if train/test design is careless.

## Next Required Action

Architect and prepare a bounded E4-N dual-source training screen for the existing-feature candidate batch:

`GOOD`, `HELLO`, `SORRY` controls + `HAVE`, `KNOW` candidates.

The package should train/evaluate without local re-extraction first, preserve ASL Citizen/local provenance, and report whether adding `HAVE` and `KNOW` damages the core or fails cross-source/held-out behavior. Long training should be user-run.

## Related Context Files

- `context/recognition_upgrade/E4_L_RESULT_AND_SCREENING_PIVOT.md`
- `context/recognition_upgrade/ARCHITECTURE_DECISIONS.md`
- `context/recognition_upgrade/DATASET_UPGRADE_PLAN.md`
- `context/recognition_upgrade/EXPERIMENT_MATRIX.md`
- `context/recognition_upgrade/RISK_REGISTER.md`
- `context/progress-tracker.md`
