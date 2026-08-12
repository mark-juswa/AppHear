# E2e All-Hand Gold Audit Smoke Result

## Purpose

Evaluate the completed six-frame human annotation smoke, verify that the revised reviewer produces usable gold data, and determine whether the registered IoU scorer is valid for the exact MediaPipe Tasks outputs stored by AppHear.

## Scope

This result covers six ASL Citizen frames only. It is a tooling and metric-contract smoke, not an accuracy estimate, gate decision, or authorization to change Android, MediaPipe, the recognizer, or model assets.

## Current Status

SUPERSEDED BY `E2E_LANDMARK_ASSOCIATION_RESULT.md`; HUMAN REVIEW REMAINS VALID.

## Verified Annotation Result

- Six of six rows completed.
- Zero rows quarantined and zero structural errors.
- Nine visible hand instances across five visible-hand frames.
- Four two-hand frames, one one-hand frame, and one no-hand frame.
- All source-mirror and anatomical-side values safely remain `unknown`.
- All five visible-hand frames were marked motion-blurred.
- One frame was marked occluded and one near-face.
- Visual overlay inspection found the human boxes plausible and consistent with the instruction to include the visible hand contour and fingertips.

## Raw MediaPipe Presence Result

The exact IMAGE-mode outputs contained six landmark instances:

- g001: one gold hand, one MediaPipe instance;
- g002: two gold hands, two MediaPipe instances;
- g003: two gold hands, one MediaPipe instance;
- g004: two gold hands, one MediaPipe instance;
- g005: zero gold hands, zero MediaPipe instances;
- g006: two gold hands, one MediaPipe instance.

This supports the prior visual finding that incomplete two-hand detection is a real failure mode. It does not show an any-hand dropout in these five visible-hand smoke frames.

## Rejected IoU Result

The current scorer reported IoU-based instance recall 3/9 at 0.50, zero at 0.75, and a 50% false-box rate. These numbers are not valid detector-accuracy measurements.

Reason: `HandLandmarkerResult` in this pipeline stores 21 hand landmarks and handedness, not the internal palm-detector rectangle. `pipeline/tracking/e2e_pilot.py` constructs the magenta rectangle from the min/max landmark coordinates. Human gold boxes instead contain the full visible hand contour. The two rectangles have different semantics; a correct landmark instance can therefore have low IoU against a correct human contour box.

The overlay confirms this on g001 and g002: every MediaPipe landmark envelope belongs to the correct visible hand, but the smaller internal envelope falls below IoU 0.50 because the human box includes the full contour.

## Diagnostic Association

A temporary center-inside-gold association, used only to diagnose the contract, matched:

- six of nine visible hand instances;
- at least one instance in five of five visible-hand frames;
- both hands in one of four two-hand frames;
- zero unmatched predictions.

These correspond to 66.7% instance presence, 100% any-hand frame presence, and 25% both-hands-complete presence in this deliberately tiny smoke. They must not be reported as accuracy or used for a gate.

## Architecture Decision

- Accept the human reviewer and annotation schema.
- Reject raw landmark-envelope IoU as the primary detector-presence metric.
- Keep full-contour gold boxes; do not ask the developer to redraw this smoke.
- Before generating 150 frames, store all 21 raw landmarks for each MediaPipe instance.
- Define and test a landmark-instance-to-gold association using palm-center containment, in-box landmark fraction, and one-to-one matching.
- Retain IoU only as a secondary localization diagnostic after any padding rule is explicitly calibrated and frozen.
- Re-score these same six frames and inspect overlays before authorizing the full audit.

## Source Of Truth Files

- `pipeline/tracking/e2e_gold.py`
- `pipeline/tracking/e2e_gold_review.py`
- `pipeline/tracking/e2e_gold_audit.py`
- `E2E_GOLD_AUDIT_WORKFLOW.md`
- `E2E_ASL_CITIZEN_PILOT_RESULT.md`
- `scratchpad/e2e_gold_audit_smoke_20260726/gold_review.csv`
- `scratchpad/e2e_gold_audit_smoke_20260726/internal_index.csv`
- `scratchpad/e2e_gold_audit_smoke_20260726/audit_summary.json`
- `scratchpad/e2e_gold_audit_smoke_20260726/smoke_gold_vs_mediapipe.jpg`

## Artifact Hashes

- gold review: `5E4CA434B1DAB528E147079D31B6296D1F03129A026CC61AFFD417B9B7DFEFC0`
- internal index: `781C5498A63E2B55F05EE70740FF0BBF72B72204B61F2F1CA14B10D3394A7ECF`
- rejected IoU summary: `D86D9321573458A788D8C83C79539FD70AE71C4457170550049E2A6E85D447BE`
- visual overlay: `AE885B520195E4A6D75A2F884FAC1945F0C45B0D9AAB9430436E01FF52049F2E`

## Assumptions

- The reviewer boxes reflect the developer's intended visible-hand contour.
- A landmark instance whose robust palm center belongs inside one gold hand is a detector-presence candidate; the exact acceptance rule is not yet frozen.
- This failure-focused research path may overrepresent blur and two-hand difficulty.

## Open Questions

- Which landmark subset and containment threshold best associates an instance without accepting a wrong hand?
- Should occluded or edge-clipped gold boxes use a different in-box landmark-fraction threshold?
- Can the Tasks graph expose an actual detector ROI without replacing the task bundle?
- How should non-signing negative frames be sampled for false-positive evaluation?

## Risks

- Freezing center containment without adversarial tests could accept a wrong or overlapping hand.
- Using IoU despite the semantic mismatch would understate valid detections and inflate false boxes.
- Using six frames as an accuracy result would be statistically invalid.
- Generating the full audit before storing landmarks would require avoidable re-extraction.

## Next Required Action

Revise the internal prediction schema and scorer for landmark-instance association, add known-answer tests for one-hand, two-hand, overlap, and false-instance cases, then re-score these same six annotations. Do not generate the 150-frame audit yet.

## Last Updated

2026-07-26