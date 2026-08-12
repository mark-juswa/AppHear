# C0-A HaGRID Smoke Result

## Purpose

Record the completed HaGRID YOLOv10n hand-detector smoke and threshold sweep so future agents do
not confuse the reference checkpoint with an approved AppHear detector.

## Scope

This result covers offline C0-A smoke inference only. It does not authorize full C0-A gate
inference, detector training, Android integration, recognizer retraining, feature-schema changes, or
production model replacement.

## Current Status

COMPLETE - NO-GO FOR DIRECT PROMOTION / FULL C0-A GATE NOT STARTED.

Last updated: 2026-07-28.

## Verified Project References

- Smoke run: `artifacts/recognition_upgrade/e2e_c0/c0a_hagrid_smoke_01`.
- Checkpoint: `artifacts/recognition_upgrade/e2e_c0/checkpoints/hagridv2_yolov10n_hands/YOLOv10n_hands.pt`.
- Checkpoint SHA-256:
  `C6EA3B5F0323D94D9EE461EBB2BCB21BD1C743B19B5AA6A008D118D83C97DC03`.
- Preflight check: `artifacts/recognition_upgrade/e2e_c0/c0a_hagrid_smoke_01/preflight_check.json`.
- Smoke manifest: `artifacts/recognition_upgrade/e2e_c0/c0a_hagrid_smoke_01/smoke_manifest.csv`.
- Threshold sweep summary:
  `artifacts/recognition_upgrade/e2e_c0/c0a_hagrid_smoke_01/hagrid_smoke_threshold_sweep_summary.json`.
- Preserved prediction files:
  `artifacts/recognition_upgrade/e2e_c0/c0a_hagrid_smoke_01/predictions/hagrid_yolov10n_hands_smoke_conf_*.jsonl`.
- Hard-case panel:
  `artifacts/recognition_upgrade/e2e_c0/c0a_hagrid_smoke_01/hagrid_smoke_hard_cases_conf_0p50.png`.

## Result Summary

The smoke set contained six AppHear positive gold frames and twenty reviewed no-visible-hand N0
negative frames. It was intentionally small and is not the full C0-A gate.

| Confidence | Positive detected | N0 false-positive frames | Interpretation |
|---:|---:|---:|---|
| 0.01 | 5/6 | 15/20 | High recall, unusably noisy negatives |
| 0.05 | 4/6 | 11/20 | Recall drops; false positives remain high |
| 0.10 | 4/6 | 8/20 | Still far above the false-ROI target |
| 0.25 | 4/6 | 5/20 | False positives still high; recall unchanged |
| 0.50 | 4/6 | 4/20 | Still 20% N0 frame false-positive rate |
| 0.75 | 3/6 | 2/20 | False positives reduce, but recall collapses |
| 0.90 | 1/6 | 0/20 | N0 clean only after losing most positives |

Missed positive IDs at the less noisy 0.50 threshold: `g031`, `g105`.

Persistent N0 false positives at 0.50: `n0_0178`, `n0_0244`, `n0_0188`, `n0_0363`.

## Interpretation

The threshold curve is the main finding: the HaGRID YOLOv10n hand detector cannot remove no-hand
false positives on this AppHear smoke set without losing real AppHear hand frames. This does not
prove that independent hand detection is impossible, but it is enough to reject direct promotion of
this checkpoint as AppHear's hand-presence gate.

Because the smoke is below the C0-A transfer-go direction and the checkpoint has unresolved
AGPL/licensing/export constraints, running the full C0-A gate with this checkpoint is low value
unless it is used only as a research baseline.

## Architecture Decisions

- Treat HaGRID YOLOv10n as a reference baseline only.
- Do not promote HaGRID YOLOv10n to Android, TFLite, or production recognizer work.
- Do not start C0-B detector training from this result alone.
- Follow the C0 stop rule: compare an AppHear-domain/mobile-compatible detector path against an
  upper-body or full-frame RGB fallback before investing in detector training.
- Keep MediaPipe as the landmark provider when it succeeds, but do not rely on it as the sole ROI
  authority.

## Assumptions

- The smoke selection is representative enough to detect gross transfer failure but not large enough
  for final detector statistics.
- The no-hand N0 annotations are still the correct false-ROI reference.
- P1 visible-hand non-sign clips remain diagnostic positives, not negative examples.

## Open Questions

- Are the persistent N0 false positives true annotation/review edge cases or genuine detector
  hallucinations on hand-like objects/body parts?
- Would a production-compatible detector trained with AppHear-domain negatives avoid the same false
  positives without losing edge/blur recall?
- Would a full/upper-body RGB stream bypass the hand-box bottleneck enough to be a better E3 route?
- How much additional labeled AppHear hand-box data would be required for a detector pilot?

## Risks

- Tuning repeatedly on the tiny smoke set would overfit the decision.
- Training a detector immediately could spend effort on a route that may still fail Android cost,
  false-positive, or licensing gates.
- Abandoning independent detection too early could leave MediaPipe's known 66.30% hand-instance
  recall problem unresolved.

## Next Required Action

Prepare a bounded C0 decision package that compares two routes before any long training:

1. an AppHear-domain, production-compatible single-class hand detector pilot design using frozen
   P0/N0/P1 annotations plus additional training-only boxes; and
2. a landmark-independent upper-body/full-frame RGB fallback design that can support E3 if hand-box
   detection remains unreliable.

Do not start full C0-A inference, C0-B training, E3 training, or Android integration until that
decision package is reviewed.

