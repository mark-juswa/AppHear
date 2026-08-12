# E2e-C0 N0/P1 Capture Result

## Purpose

Freeze the reviewed detector-evaluation fixtures required by the E2e-C0 independent hand-detector
screen and prevent future agents from reconstructing their status from terminal logs.

## Scope

This document records capture, sampling, review, validation, provenance, and limitations only. It
does not report detector accuracy, authorize detector training, start E3, or change Android.

## Current Status

PASS / N0 AND P1 CAPTURE GATES COMPLETE / C0-A PREFLIGHT NEXT.

Last updated: 2026-07-27.

## Verified Results

### N0: No Visible Hands

- Final run: `artifacts/recognition_upgrade/e2e_c0/n0_capture_06`.
- Reviewed rows: 630 deterministic 1 FPS frames.
- Eligible no-hand frames: 613.
- Visible-hand contamination exclusions: 16.
- Quarantined frames: 1.
- Capture provenance: 57 clips, 876.327 seconds, six participants, five devices, five
  environments, front camera.
- `reviewed_manifest.csv` SHA-256:
  `953D2FCA81D171016C8345A8FB6B524931A67C7420B8E9ABFB8CAF2421A10291`.
- `gold_review.csv` SHA-256:
  `0CB3160B396DC2A078ADEDD6BD81301AE511B41FFD1FA722EC4FE3D6B3DB47CB`.
- `capture_summary.json` SHA-256:
  `E7EF3C7E39A9330801B50BC37093AA4DC10D17CA8875ADDEB527D3606A01ECDD`.

### P1: Visible Hands, Not Signing

- Final run: `artifacts/recognition_upgrade/e2e_c0/p1_capture_03`.
- Reviewed rows: 140 deterministic 1 FPS frames.
- Eligible visible-hand/non-sign frames: 108.
- Gold hand instances: 172.
- No-visible-hand exclusions: 32.
- Capture provenance: 30 clips, 678.721 seconds, two participants, two devices, one indoor
  environment, front camera.
- Every eligible row has a non-empty valid hand-box payload.
- `reviewed_manifest.csv` SHA-256:
  `B2D5FB8DBF8F94098146D023648A7FBF79003E0F06EDAD73CE5880E9BBC95FDD`.
- `gold_review.csv` SHA-256:
  `73A6B8F5EF8D452D461BA37ACB40922DDC1499DE9CF0866EB206BF5EC9713F03`.
- `capture_summary.json` SHA-256:
  `79992F67459BDD25D694FD4F237A7A91E201FF64D166FF590CE0AC52B3ED8649`.

## Annotation Carry-Forward Integrity

The default sample sizes left too few eligible rows after legitimate exclusions. Existing work was
not copied by row number:

- N0 expanded from 600 to 630 rows with the same seed. All 57 source-video hashes and all 600
  shared extracted-image hashes matched before transferring 600 annotations.
- P1 expanded from 110 to 140 rows with the same seed. All 30 source-video hashes and all 110
  shared extracted-image hashes matched before transferring 110 annotations.
- Each final run preserves the untouched destination template as
  `gold_review.pre_carry_forward_backup.csv`.
- Newly selected rows were reviewed manually before the final validator ran.

## Interpretation

- N0 is the C0-A hand-absent false-positive fixture.
- P1 is a diagnostic positive set for ordinary hands outside formal signing.
- P1 must never be treated as an N0 negative set because visible idle hands are true detector
  positives.
- Passing these gates proves fixture completeness, not detector quality or recognition accuracy.
- The frozen 150-frame ASL Citizen all-hand gold audit remains the primary positive transfer set.

## Source-Of-Truth Files

- `artifacts/recognition_upgrade/e2e_c0/n0_capture_06/`
- `artifacts/recognition_upgrade/e2e_c0/p1_capture_03/`
- `E2E_C0_DETECTOR_SCREENING_PLAN.md`
- `E2E_C0_CAPTURE_RUNBOOK.md`
- `E2E_ALL_HAND_GOLD_RESULT.md`
- `pipeline/tracking/e2e_c0_capture.py`

## Related Context Files

- `README.md`
- `EXPERIMENT_MATRIX.md`
- `ARCHITECTURE_DECISIONS.md`
- `IMPLEMENTATION_READINESS_CHECKLIST.md`
- `RISK_REGISTER.md`
- `OPEN_QUESTIONS.md`
- `../progress-tracker.md`
- `../../memory.md`

## Architecture Decisions

- Freeze N0/P1 before checkpoint acquisition or C0-A inference.
- Keep all detector work offline and isolated from the production recognizer.
- Preserve the C0-A no-training transfer screen before any C0-B training.
- Do not tune a detector on the frozen positive, N0, or P1 evaluation fixtures.

## Assumptions

- Participant consent and folder metadata supplied during capture are accurate.
- The manual boxes represent all visible hand extents according to the runbook.
- Front-camera-only capture is acceptable for this bounded screen but does not establish back-camera
  robustness.

## Open Questions

- Whether the HaGRID checkpoint license chain is acceptable for research and incompatible with a
  proprietary production path.
- Whether the checkpoint exposes reproducible hand-only boxes and confidence scores.
- Whether C0-A transfers across ASL blur, clipping, occlusion, and two-hand interaction.
- Whether P1 needs broader environment coverage after the first transfer result.

## Risks

- N0 frames remain correlated within clips despite deterministic 1 FPS sampling.
- P1 covers only two participants, two devices, one indoor environment, and front-camera capture.
- Repeated threshold tuning on these fixtures would invalidate their evaluation role.
- A research checkpoint may pass technically but remain unusable for production licensing/export.

## Next Required Action

Resolve and freeze the exact HaGRID reference checkpoint, dependencies, preprocessing, output
contract, and license evidence in an isolated C0-A environment. Then run the registered
six-positive/twenty-negative smoke and stop for review before full inference.
