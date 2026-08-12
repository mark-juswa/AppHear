# E2e All-Hand Gold Audit Result

## Purpose

Record the corrected, side-independent MediaPipe hand-instance reliability result that decides whether AppHear can continue using MediaPipe as its sole hand-ROI source.

## Scope

This is an experiment result and architecture gate. It does not change Android, production MediaPipe settings, schema 3.0, model assets, datasets, or recognition behavior.

## Current Status

COMPLETE / VALID FOR ENGINEERING GATE / NO-GO FOR MEDIAPIPE AS SOLE ROI PROVIDER.

## Verified Project References

- Source run: `F:/ASL DATASET/ASL CITIZEN/derived/apphear3/recognition_upgrade/e2e_all_hand_gold_v1/engineering_01`.
- 150 unique ASL Citizen clips, 41 signers, 120 train and 30 validation clips.
- 50 frames each at 25%, 50%, and 75% through the annotated sign span.
- Human gold: every visible hand instance, independent of MediaPipe handedness.
- Prediction schema: all 21 normalized MediaPipe hand landmarks per detected instance.
- Association: palm center inside human box, at least 50% of landmarks inside, exact maximum-cardinality one-to-one matching.
- Final source review SHA-256: `53e3db0dceeeb4b5a991be132bdce1fe489d82d670daa662023f6707852835d9`.
- Pre-adjudication review backup: `gold_review.pre_e2e_gold_adjudication_engineering_01.csv`.
- Provisional report backup: `audit_summary.provisional_pre_adjudication.json`.
- Final report: `audit_summary.json`.

## Annotation Adjudication

The first review undercounted blurred and clipped hands. A separate blinded correction pass re-reviewed all 88 rows initially labeled below two hands. A final two-frame pass corrected `g031` and removed a logically invalid zero-hand quality flag from `g090`. Hash-guarded merges preserved both source reviews.

The correction changed the gold set from 170 to 184 visible hand instances, from 108 to 117 visible-hand frames, and from 62 to 67 two-hand frames. The provisional metrics were optimistic and are not authoritative.

## Final Metrics

| Metric | Result | 95% Wilson interval | Registered gate | Decision |
|---|---:|---:|---:|---|
| Visible hand-instance recall | 122/184 = 66.30% | 59.20-72.74% | >=95% | No-go |
| Any-hand frame recall | 91/117 = 77.78% | 69.43-84.36% | diagnostic | Insufficient |
| Complete two-hand recall | 31/67 = 46.27% | 34.86-58.08% | implied by instance gate | No-go |
| Unmatched prediction rate | 0/122 = 0% | not used as a universal precision claim | <=2% false ROI | Pass on this bounded set only |
| Selected zero-hand frame FP rate | 0/33 = 0% | 0-10.43% | separate negative audit required | Inconclusive |

All 122 MediaPipe predictions associated with a visible human hand. The dominant problem is missing hand instances, not spurious instances.

## Failure Subgroups

| Subgroup | Instance recall | Other evidence |
|---|---:|---|
| Clear | 52/64 = 81.25% | any-hand 89.74%; two-hand complete 68.00% |
| Motion blur | 70/120 = 58.33% | any-hand 71.79%; two-hand complete 33.33% |
| Occluded | 13/25 = 52.00% | two-hand complete 33.33% |
| Edge clipped | 8/31 = 25.81% | any-hand 42.11%; two-hand complete 0% |
| Partial visibility | 1/6 = 16.67% | three frames only; high uncertainty |
| One visible hand | 35/50 = 70.00% | 15 complete misses |
| Two visible hands | 87/134 = 64.93% | 31/67 frames complete |
| Train source split | 97/147 = 65.99% | consistent with validation |
| Validation source split | 25/37 = 67.57% | only 30 frames |
| Span q25 | 46/71 = 64.79% | any-hand 71.74% |
| Span q50 | 46/65 = 70.77% | any-hand 87.50% |
| Span q75 | 30/48 = 62.50% | any-hand 74.19% |

The train/validation and sign-span results are similar enough that the failure cannot be explained by one split or one sampled sign phase. Motion blur, edge clipping, occlusion, and two-hand completeness are the principal measured weaknesses.

## Architecture Decision

- Reject MediaPipe IMAGE as the sole authority for hand ROI availability.
- Do not repeat threshold tuning: E2d already rejected its recall/false-ROI trade-off.
- Do not promote VIDEO/LIVE_STREAM as the fix: E2c showed only small gains and failed gates.
- Do not rely on static pose fallback: E2b recovered crops were only 23.7% usable.
- Retain MediaPipe as the preferred 21-landmark provider whenever it succeeds.
- Add a detector-agnostic ROI manager and evaluate an independent single-class hand detector, with anatomical identity assigned separately from body geometry and temporal continuity.
- Keep E3 hybrid recognition training blocked until reliable ROI coverage passes its gate.

## Engineering Interpretation

This audit isolates detection from left/right identity. Correcting mirror or handedness semantics cannot recover the 62 missing visible hand instances. Identity and CameraX coordinate fixtures remain required before production schema changes, but they are not a sufficient remedy for the measured recall failure.

The zero observed unmatched predictions do not establish a production false-positive rate. The 33 zero-hand frames came from annotated sign spans, not a representative non-signing stream. E2e-C must include a dedicated non-signing negative set.

## Next Required Action

Architect and run E2e-C0, a bounded independent hand-detector screening experiment on the same 150-frame gold set plus a registered non-signing negative set. Compare candidate single-class detectors without recognizer training. Measure instance recall, complete two-hand recall, false ROI rate, edge/blur subgroups, latency, model size, and Android export feasibility. Advance only a candidate that materially closes the gap toward 95% recall without exceeding 2% false ROI.

## Source-Of-Truth Files

- `pipeline/tracking/e2e_gold.py`
- `pipeline/tracking/e2e_gold_review.py`
- `pipeline/tracking/e2e_gold_adjudicate.py`
- `pipeline/tracking/e2e_gold_audit.py`
- `E2E_MEDIAPIPE_RELIABILITY_PLAN.md`
- `E2E_GOLD_AUDIT_WORKFLOW.md`
- `E2E_LANDMARK_ASSOCIATION_RESULT.md`
- `E2B_PHASE_A_RESULT.md`
- `E2C_TEMPORAL_TRACKING_RESULT.md`
- `E2D_DETECTOR_OPERATING_POINT_RESULT.md`

## Related Context Files

- `README.md`
- `ARCHITECTURE_DECISIONS.md`
- `EXPERIMENT_MATRIX.md`
- `EVALUATION_AND_ACCEPTANCE_GATES.md`
- `RISK_REGISTER.md`
- `ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Assumptions

- The 150 pipeline-eligible frames estimate the AppHear ASL Citizen domain but not raw clips that failed preprocessing.
- One frame per clip supports instance recall but not temporal dropout or ID-switch measurement.
- Human boxes are authoritative after adjudication; one-reviewer variance remains possible.

## Open Questions

- Which independent detector offers the best recall/latency/export trade-off on Android?
- How much additional hard-frame annotation is needed for detector fine-tuning?
- What false-positive rate appears on genuine non-signing video?
- Can a sparse detector plus causal tracker sustain the approximately 15 FPS Android target?

## Risks

- Public hand detectors may not transfer to ASL motion blur, crossings, or edge hands.
- A detector may improve recall while increasing false ROIs, latency, heat, or battery use.
- The current gold set is too small to train a detector from scratch.
- Independent detection still requires coordinate, identity, and temporal-association validation.

## Last Updated

2026-07-26