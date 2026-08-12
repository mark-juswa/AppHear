# E4-A Landmark Generalization And Data-Quality Audit Result

- **Purpose:** Record the completed E4-A audit and choose the next evidence-based step after E3-C no-go.
- **Scope:** Offline analysis only. No Android runtime, production recognizer, model asset, feature schema, training run, or dataset file was changed.
- **Current status:** Completed on 2026-07-29. Final check passed.
- **Verified project references:** `pipeline/rgb/e4_a_generalization_audit.py`, `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01/summary.json`, `class_reliability.csv`, `confusion_groups.csv`, `data_quality_support.csv`, `signer_generalization.csv`, `vocabulary_recommendation.md`, and `check_report.json`.
- **Source-of-truth files:** This result document, `E4_A_LANDMARK_GENERALIZATION_PLAN.md`, `E3_C_RESULT.md`, `E3_B6_RESULT.md`, `E3_B7_RESULT.md`, and the E4-A run directory named above.
- **Related context files:** `README.md`, `EXPERIMENT_MATRIX.md`, `DATASET_UPGRADE_PLAN.md`, `OPEN_QUESTIONS.md`, `RISK_REGISTER.md`, and parent `../progress-tracker.md`.

## Verified Run

- **Run directory:** `artifacts/recognition_upgrade/e4_generalization/e4_a_landmark_data_audit_01`.
- **Runner:** `pipeline/rgb/e4_a_generalization_audit.py`.
- **Final check:** passed with no missing outputs.
- **Classes audited:** 50.
- **Primary evidence:** E3-B5 analysis outputs, E3-B6 metrics, E3-B7 metrics, E3-C metrics, frozen manifests, and selected-class support.
- **No long process:** the audit used existing artifacts only; it did not train models or extract landmarks/RGB.

## Output Files

- `inventory.json`
- `class_reliability.csv`
- `class_reliability.md`
- `confusion_groups.csv`
- `confusion_groups.md`
- `signer_generalization.csv`
- `signer_generalization.md`
- `data_quality_support.csv`
- `data_quality_support.md`
- `reliable_vocabulary_v0.csv`
- `hard_confusion_set_v0.csv`
- `vocabulary_recommendation.md`
- `next_experiment_decision.md`
- `summary.json`
- `summary.md`
- `README_RUN.md`
- `check_report.json`

## Result Summary

| Tier | Count | Meaning |
|---|---:|---|
| `candidate_keep` | 4 | Stronger held-out landmark evidence with no dominant confusion under the conservative gate |
| `borderline_collect_more` | 15 | Some useful signal, but needs more signer evidence or stability before retrain/promotion |
| `confusion_review` | 8 | Stable dominant confusion requires video/label/variant review |
| `drop_or_defer` | 6 | Weak current landmark evidence for near-term release |
| `needs_visual_evidence` | 17 | Landmark evidence is inconclusive; video review is needed before blaming landmarks or RGB absence |

Candidate keep classes:

- `SWITZERLAND`
- `COUCH`
- `CURLYHAIR`
- `DOWNSIZE1`

Borderline classes include examples such as `PEEKABOO`, `BEE1`, `BOTH`, `SHARK1`, `LETTUCE1`, `SENTENCE2`, `SHAVE1`, `TWINS1`, `EVERYYEAR`, and others. These are not rejected; they need more signer evidence or stability review.

## Major Confusion Groups

The strongest confusion groups requiring review are:

- `DEAF1 <-> TWINS1`: 29 total confusions, max confusion rate `0.6667`.
- `EVERYYEAR <-> TAKECARE`: 25 total confusions, max confusion rate `0.6667`.
- `CROSS3 <-> WHALE`: 29 total confusions, max confusion rate `0.5000`.
- `ROCKINGCHAIR1 <-> TRACTOR`: 26 total confusions, max confusion rate `0.5000`.
- `BASEBALLCAP <-> LETTUCE1`: 23 total confusions, max confusion rate `0.5000`.
- `BOXING <-> TAKECARE`: 13 total confusions, max confusion rate `0.5000`.
- `EDIT1 <-> INDEPENDENT`: 11 total confusions, max confusion rate `0.5000`.
- `ELEVATOR1 <-> INDEPENDENT`: 9 total confusions, max confusion rate `0.5000`.

These causes are not automatically known. They must be reviewed against videos/labels and classified as label variant, insufficient data, landmark geometry limitation, timing/boundary issue, or unknown.

## Important Tooling Gap

E4-A can compute per-signer support from `pilot_manifest.csv`, but it cannot honestly compute per-signer accuracy from the current E3 artifacts because stable per-clip predictions are not persisted for every branch/seed.

This is now a required tooling gap before any signer-level accuracy claim. Future E4 tooling should either persist per-clip predictions during evaluation or regenerate them from saved checkpoints.

## Decision

The next decision is **E4-C targeted collection then E4-B**, not immediate retraining.

Reason:

- Only 4 of 50 classes passed conservative keep criteria.
- 15 classes are plausible but need more signer evidence or stability.
- 8 classes have dominant confusion patterns requiring label/video review.
- 31 classes are hard/defer/visual-evidence categories under the current landmark evidence.
- Training immediately on all 50 classes would likely repeat the same generalization failure.
- Training a cleaned subset with only 4 candidate classes is too small for the intended AppHear milestone unless the user explicitly wants a very small demo vocabulary.

## Recommended Next Step

Prepare **E4-C targeted data and label-review plan** before E4-B retraining.

E4-C should:

1. Select the 4 candidate-keep classes as anchors.
2. Select the best borderline classes for expansion, not all 50 classes.
3. Review the top confusion groups against raw videos and labels.
4. Produce a targeted collection list with glosses, signer counts, repetitions, device/environment variation, and review requirements.
5. Decide whether the next retrain should use a 15-25 class reliable-first vocabulary or wait for more data.

## Architecture Decisions

- Do not retrain the 50-class recognizer blindly.
- Do not return to E3-C upper-body RGB fusion.
- Do not promote E3-B6 to Android despite being the strongest current landmark result.
- Use E4-A output to guide targeted data/label work first.
- Any future E4-B retrain must use a reviewed class list and must include per-class, per-signer, confusion, calibration, and no-sign/OOV gates.

## Assumptions

- The conservative tiering is a decision aid, not a final linguistic judgment.
- Some classes may be recoverable with more signer diversity or label/variant cleanup.
- Some classes may require visual hand-shape evidence, but E4-A does not prove which ones without video review.

## Risks

- The class tiers can be overfit to the E3-B5 frozen split if treated as permanent truth.
- Important product signs may be weak and need collection, not removal.
- Manual video/label review may require ASL fluency that the current tooling does not provide.
- Per-signer accuracy remains unavailable until per-clip predictions are persisted or regenerated.

## Next Required Action

Architect E4-C targeted data and label-review plan from E4-A outputs. Do not start E4-B retraining until the target class list and data/label actions are reviewed.
