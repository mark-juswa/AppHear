# Post-E6 Architecture Review

**Purpose:** Challenge the original recognition-upgrade architecture against completed E1-E6
evidence and select one non-duplicate next experiment.

**Scope:** Architecture and experiment planning only. No extraction, annotation, training, schema
change, model export, Android change, or production migration is authorized.

**Current status:** COMPLETE / ONE NEXT EXPERIMENT SELECTED / IMPLEMENTATION NOT STARTED.

**Last updated:** 2026-08-09.

## Evidence Labels

- **Verified project evidence:** measured in AppHear artifacts or source-of-truth result files.
- **External research evidence:** supported by the cited official documentation.
- **Engineering inference:** conclusion drawn from verified evidence but not itself measured.
- **Hypothesis requiring experimentation:** must pass the registered AppHear gate.

## Executive Decision

The original global hybrid architecture is not cancelled, but it is not ready to build. The
dynamic mixed E6 route was a bounded attempt to reach a useful system without first solving RGB
ROI reliability. E6-2, E6-3, and E6-5 failed their gates; E6-6 and E6-7 therefore remain blocked.

The only high-value, materially unfinished prerequisite from the original architecture is a
production-compatible AppHear-domain hand detector. The selected next experiment is therefore
**C0-B0 AppHear-Domain Hand-ROI Detector Feasibility**. It must first prove that independent
training annotations and a reproducible TFLite export path exist. Training is not authorized until
that internal readiness gate passes.

This is not another sign classifier, vocabulary screen, threshold sweep, specialist, fusion model,
or Android integration.

## Original Target Versus Completed Evidence

| Target component | Closest completed work | Verified result | Post-E6 status |
|---|---|---|---|
| Timestamped CameraX frames | Current Android capture; E2c VIDEO tests | Temporal mode did not materially solve hand coverage; production remains IMAGE | retain timestamps as future contract; no mode-tuning rerun |
| MediaPipe hand/pose landmarks | E2/E2c/E2d/E2e | Useful structured source, but only `66.30%` visible hand-instance recall and `46.27%` complete two-hand recall on corrected gold | retain for landmarks; do not use as sole RGB ROI source |
| Reliable hand ROIs | E2b pose recovery; E2d thresholds; E2e gold; C0-A HaGRID smoke | Pose recovery, threshold/mode tuning, and HaGRID transfer all failed their gates | unresolved prerequisite |
| Structured landmark encoder | E1, E3-B4/B5/B6/B7, E6-2 | v3.0 remains the accepted control; graph/derived/global geometry replacements did not pass | retain v3.0 baseline; stop feature variants |
| Crop-free RGB stream | E3-B0/B1/B2/B3/C | Full/upper-body RGB and naive fusion generalized poorly and underperformed landmarks | exhausted in tested form; do not repeat |
| Detector-derived hand RGB | Not completed | No reliable independent ROI provider reached the prerequisite gate | blocked by C0-B0 |
| Landmark + hand-RGB fusion | E3-B3/C used upper-body frozen MobileNet evidence, not reliable hand crops | Naive fusion failed; true hand-crop fusion remains untested | blocked by ROI gate and later RGB single-stream gate |
| No-sign/OOV rejection | E4-Y through E4-AG, E5-H/I, E6-3 | Thresholds, shared accept head, MSP, energy, and pooled Mahalanobis did not provide a safe general solution | no accepted rejector; do not retune same methods |
| Confusion routing/specialists | E4-T through E4-X, E6-4/E6-5 | Small GOOD/SORRY proof passed; broader E6 KNOW/HELLO specialist failed across fresh/stress gates | evidence only; no scalable specialist layer approved |
| Boundary/continuous recognition | E4 gate work only | Isolated-window reliability and open-set safety remain unresolved | CTC/continuous work remains blocked |
| Android shadow integration | None authorized | E6-6 prerequisites absent | blocked; production recognizer remains protected |

## Assumptions Challenged

1. **More landmark engineering will fix the system.** Rejected for the next step. E3-B6/B7 and
   E6-2 already supplied materially different geometry/motion representations without a robust
   promotion result.
2. **A better threshold or distance score will provide unknown rejection.** Rejected for the next
   step. E4-T, E5-H/I, and E6-3 exhausted the tested score families on current evidence.
3. **Any RGB branch will help.** Rejected. E3 showed that weak, crop-free upper-body RGB can hurt
   fusion. RGB is useful only as a hypothesis after reliable hand crops exist.
4. **HaGRID failure disproves independent hand detectors.** Rejected. C0-A tested one generic,
   externally trained checkpoint on a tiny transfer smoke. It did not test AppHear-domain
   fine-tuning with hard negatives.
5. **C0-B can start immediately.** Rejected. Existing P0/N0/P1 boxes are frozen evaluation
   fixtures. Using them for training would contaminate the gate, and no separate approved
   training-only box manifest exists.
6. **The old Model Maker plan is automatically production-safe.** Rejected. Google currently
   documents MobileNetV2/MultiHW detector training and TFLite/INT8 export, but explicitly marks
   MediaPipe Model Maker as available and no longer actively maintained. Toolchain reproduction is
   therefore an experiment gate, not an assumption.

## Paths Removed Or Postponed

- Skip E6-6 and E6-7; they lack passed rejection and specialist inputs.
- Skip more E5-style vocabulary shrinking, sign-by-sign addition, and threshold sweeps.
- Skip more `[96,728]`, `[96,444]`, graph, or geometry subset experiments.
- Skip global/full-frame/upper-body frozen-MobileNet RGB and naive concatenation fusion.
- Skip another HaGRID YOLOv10n threshold sweep or direct production promotion.
- Postpone face landmarks, continuous CTC, language modeling, RGB recognition, fusion, and Android
  integration until the hand-ROI prerequisite passes.

## Selected Next Experiment

See `C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`.

The experiment is genuinely different from prior work because it tests an AppHear-domain,
single-class detector trained only on a new training partition with explicit no-hand hard negatives,
then evaluates it once on the frozen P0/N0/P1 fixtures. Previous C0-A used an unadapted HaGRID
checkpoint; E2 used MediaPipe landmarks/boxes; E3 used center upper-body crops.

## Go / No-Go Consequence

- **Go:** authorize a separate detector-derived crop-quality experiment. Do not train an RGB sign
  recognizer yet.
- **No-go:** retire hand-crop hybrid as the immediate mobile path. Preserve v3.0 and return to an
  explicit product-scope decision instead of inventing another model tweak.

## Protected Baseline

The baseline in `E6_0_BASELINE_FREEZE.md` remains authoritative. No production Android model,
vocabulary, schema 3.0 feature builder, confirmation policy, camera lifecycle, or sentence/UI file
may be changed by this review or C0-B0.

## Source-Of-Truth Files

- `TARGET_ARCHITECTURE.md`
- `MIGRATION_PHASES.md`
- `E2E_C0_DETECTOR_SCREENING_PLAN.md`
- `C0A_HAGRID_SMOKE_RESULT.md`
- `C0_ROUTE_DECISION_REPORT.md`
- `E3_C_RESULT.md`
- `E6_1_CONSOLIDATED_EVIDENCE_DATASET_AUDIT.md`
- `E6_COMPONENT_DECISION.md`
- `E6_0_BASELINE_FREEZE.md`

## External Sources

- Google object detector customization: https://developers.google.com/edge/mediapipe/solutions/customization/object_detector
- Google MediaPipe Object Detector for Android: https://developers.google.com/edge/mediapipe/solutions/vision/object_detector/android

## Risks

- Training-box annotation may be too expensive or insufficiently diverse.
- Domain fine-tuning may improve recall but create unacceptable false ROIs.
- The deprecated Model Maker training package may not reproduce in a stable environment.
- A detector may pass offline but exceed Android CPU, memory, or thermal budgets.
- Reliable boxes may still not make RGB sign recognition generalize.

## Open Questions

- How many independent raw videos can supply training boxes without overlapping frozen evaluation
  fixtures or prior held-out sign clips?
- Can the documented detector export path be reproduced with pinned dependencies?
- Does a 256-pixel detector retain edge, blur, small-hand, and two-hand recall?

## Next Required Action

Review and approve `C0B_APPHEAR_HAND_ROI_FEASIBILITY_PLAN.md`. If approved, implement only its
inventory, annotation, and toolchain preflight. Do not begin detector training automatically.
