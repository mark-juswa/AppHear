# E2e Landmark-Instance Association Result

## Purpose

Record the corrected MediaPipe presence-scoring contract, its non-destructive application to the completed six-frame human smoke, and the decision on full engineering-audit readiness.

## Scope

This result approves experimental data collection only. It does not claim accuracy, pass a MediaPipe gate, train a detector, change Android, or alter the production recognizer.

## Current Status

LANDMARK-ASSOCIATION SMOKE PASSED / FULL 150-FRAME ENGINEERING AUDIT AUTHORIZED.

## Verified Prediction Contract

Each MediaPipe hand prediction now records:

- handedness label and confidence;
- legacy min/max landmark envelope for visualization only;
- all 21 normalized image landmarks with x, y, and z;
- prediction schema `mediapipe_hand_21_landmarks_v1`.

`pipeline.tracking.e2e_gold --enrich-run-dir` enriches a reviewed run from its frozen center images. It backs up the old internal index and does not change `gold_review.csv`.

## Association Contract

A candidate can associate with a human full-contour hand box only when:

- the robust palm center, averaged from landmarks 0, 5, 9, 13, and 17, lies inside the gold box;
- at least 50% of the 21 landmarks lie inside the gold box.

Assignment maximizes one-to-one match cardinality first and then total landmark coverage plus normalized center proximity. Exact matching is used because a frame contains at most two gold hands and two MediaPipe instances.

Raw landmark-envelope IoU remains a secondary localization diagnostic. It is not detector presence or recall.

## Known-Answer Tests

Focused fixtures cover:

- one valid hand instance;
- palm outside the gold hand;
- two independent hands;
- an unmatched false instance;
- overlapping two-hand boxes;
- one-to-one maximum-cardinality behavior;
- mirror-adjudicated identity after geometric association;
- legacy IoU as localization only;
- invalid partial reviewer state recovery.

The complete project suite passed 169 tests. Ruff and mypy passed for the changed experimental modules.

## Corrected Six-Frame Smoke

The human gold CSV remained byte-identical during enrichment.

- accepted frames: 6;
- gold hand instances: 9;
- MediaPipe instances: 6;
- associated instances: 6/9;
- any-hand frames associated: 5/5;
- both-hands-complete frames: 1/4;
- unmatched MediaPipe instances: 0/6;
- negative frame with a prediction: 0/1.

The landmark overlay visually confirms every association. g003, g004, and g006 each contain two human-visible hands but only one MediaPipe instance. This is direct evidence of incomplete two-hand capture in the smoke.

These counts are diagnostic only. Six frames cannot support an accuracy or gate claim.

## Artifacts

- corrected summary: `scratchpad/e2e_gold_audit_smoke_20260726/audit_summary_landmark_v1.json`
- overlay: `scratchpad/e2e_gold_audit_smoke_20260726/smoke_landmark_association.jpg`
- enriched index: `scratchpad/e2e_gold_audit_smoke_20260726/internal_index.csv`
- reversible backup: `scratchpad/e2e_gold_audit_smoke_20260726/internal_index.pre_landmark_enrichment.csv`
- unchanged gold: `scratchpad/e2e_gold_audit_smoke_20260726/gold_review.csv`

## Artifact Hashes

- unchanged gold: `5E4CA434B1DAB528E147079D31B6296D1F03129A026CC61AFFD417B9B7DFEFC0`
- enriched index: `7CDF2E7CBC5CF6DED128C6F145B08D1359CE8804A489ED581CCBFDB76D3BF497`
- pre-enrichment index: `781C5498A63E2B55F05EE70740FF0BBF72B72204B61F2F1CA14B10D3394A7ECF`
- corrected summary: `243F89587573C9146B69831F91537C643AC8A50F19073A6C6859FF87ADBF176A`
- landmark overlay: `A743C343E522ADE63671A3D56205DA66522C4B50BDD95B2B368EA9699928F8CC`

## Architecture Decisions

- Approve the reviewer, full-contour gold boxes, enriched prediction schema, and association rule for the 150-frame engineering audit.
- Keep identity metrics separate and unavailable when mirror status or anatomical side is unknown.
- Keep IoU out of primary detector-presence gates.
- Manually inspect every unmatched prediction and every partial/edge-clipped unmatched gold hand before a gate decision.
- Require at least 120 accepted frames; 150 are generated to tolerate quarantine.

## Assumptions

- A robust palm center and majority landmark containment identify a complete visible hand instance reliably enough for engineering-audit association.
- Partial or edge-clipped hands may violate the strict rule and therefore require subgroup inspection.
- The audit estimates AppHear behavior on the sampled ASL Citizen domain, not universal ASL performance.

## Open Questions

- What are the corrected overall, two-hand, cadence, blur, occlusion, and near-face rates on 120-150 frames?
- How many partial or edge-clipped cases need manual association adjudication?
- Does incomplete two-hand capture remain the dominant error on a detector-independent sample?
- Is the failure severe enough to require pose ROI refinement or an independent detector?

## Risks

- Partial hands can have a valid detected instance whose predicted palm lies outside the visible contour box.
- Positive-control sampling cannot by itself establish non-signing false-positive performance.
- One annotator can introduce contour-boundary variance, although primary association is less sensitive than IoU.
- The 50% containment threshold remains an engineering rule and must be stress-tested on the full audit's ambiguous cases.

## Next Required Action

Generate the deterministic 150-frame engineering package. The developer performs the resumable review. After completion, run the corrected scorer and manually inspect all unmatched and partial/edge cases before applying gates.

## Last Updated

2026-07-26