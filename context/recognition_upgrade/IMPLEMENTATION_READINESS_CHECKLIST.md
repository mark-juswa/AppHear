# Implementation Readiness Checklist

**Purpose:** Hard stop before any upgrade code, model, dataset transform, or Android asset change.
**Status:** NOT READY / C0-B0 TARGETED TOP-UP SCAN READY. **Last updated:** 2026-08-10.

## Plan Approval

- [x] Developer approved `E2E_C0_DETECTOR_SCREENING_PLAN.md` on 2026-07-27.
- [ ] `ARCHITECTURE_DECISIONS.md` has no unresolved implementation-blocking decision.
- [ ] Risks have owners; rights/consent review is complete.
- [ ] Pilot vocabulary and linguistic reviewer are named.

## Baseline

- [ ] E0 hashes, metrics, configs, splits, and environment are frozen.
- [ ] Baseline Git tag/assets restore successfully.
- [ ] Current Android build/tests and device smoke pass.
- [ ] Test set access/promotion policy prevents repeated tuning.

## Experiment Contract

- [x] Corrected 150-frame all-hand gold audit and MediaPipe sole-ROI no-go are frozen.
- [x] E2e-C0 candidates and N0/P1 contracts are approved.
- [x] N0 and P1 reviewed manifests pass the capture validator.
- [x] C0-A HaGRID smoke threshold sweep is recorded as no-go for direct promotion.
- [x] C0 route decision selected staged two-branch comparison with E3-B0 RGB feasibility first.

- [ ] New branch, directories, schema ID, model names, flags, and reports are defined.
- [x] E1 sanity/fairness protocol completed with GCN no-go; TCN remains the future landmark control.
- [ ] Metrics and go/no-go thresholds are machine-readable where practical.
- [ ] No production asset/config path is an experiment output.

## Feature/Data Contract

- [ ] Raw-video provenance, timestamps, labels, signers, boundaries, and splits are audited.
- [ ] Crop/coordinate/missingness/time semantics are frozen.
- [ ] Python source-of-truth and Kotlin golden-parity design are approved.
- [ ] `/imprint` is scheduled for any adopted contract.

## Android

- [ ] Supported TFLite ops and INT8 export smoke pass before long training.
- [ ] CPU fallback, async load, memory, APK size, p50/p95, thermal, battery plan exists.
- [ ] Shadow mode and instant fallback are testable.
- [ ] Current CameraX lifecycle/UI/confirmation remain untouched in initial experiments.

## Evidence, Assumptions, Risks, Open Questions, Next Action

- **Evidence:** all linked project and research sources in this folder.
- **Assumption:** planning approval does not authorize production replacement.
- **Risk:** beginning crop/runtime work before E1/E2 creates confounded sunk cost.
- **Open questions:** listed in `OPEN_QUESTIONS.md`.
- **Next action:** prepare the E3-B0 RGB feasibility package and preflight script. Full E3 training, detector training, and Android integration remain blocked.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.

## Post-E6 C0-B0 Readiness Addendum - 2026-08-09

- [x] E1-E6 duplicate paths mapped and exhausted variants identified.
- [x] E6-6/E6-7 held because required components did not pass.
- [x] One next experiment selected and documented.
- [x] User approved C0-B0 Stage 1.
- [x] Training-only source inventory excludes frozen P0/N0/P1 by source path/hash and protected signer.
- [x] Annotation schema and review protocol passed the 24-frame review smoke.
- [x] Pinned Linux/Python 3.10 detector environment completes one-epoch train/export/reload smoke.
- [x] Optional MediaPipe proposals remain untrusted and human-reviewed; two-frame preparation smoke passed.
- [x] Source/signer-balanced 300-frame annotation pilot is prepared and structurally checked.
- [x] All 300 frames are human-reviewed and difficult-condition coverage is measured.
- [x] Independent, resumable 900-frame hard-condition miner and 100-frame package builder pass local smoke.
- [x] E6 negative reuse audit blocks all 547 overlapping development-negative windows.
- [x] Full 900-frame scan and structurally valid 100-frame package are complete with zero protected overlap.
- [x] Human review completed all 100 mined frames with 132 gold boxes and zero validation errors.
- [x] Proposal-audit metadata defect repaired without changing reviewed gold; corrected audit recorded.
- [x] Combined 400-frame set contains reviewed positives, 67 no-hand frames, two-hand and all named condition flags.
- [ ] Partial/edge and hand-like-negative diversity is sufficient for production claims; current coverage remains sparse.
- [ ] An independent dedicated hand-like/no-hand negative source is identified and reviewed.
- [x] ASL Citizen license audited: internal non-commercial research only; distribution/production use blocked.
- [ ] Local supplementary consent/release rights are documented.
- [x] Consolidated signer/source-disjoint Stage 2 research manifest passes leakage checks: `400`
  rows, `312/88` train/development, zero signer or protected-lineage overlap.
- [x] User separately approved internal research/development-only Stage 2 detector training on
  2026-08-10; production, redistribution, Android integration, and recognizer replacement remain
  unauthorized.
- [x] Deterministic hard-linked COCO packages exist for nested MobileNetV2-256 `25/50/100%`
  learning-curve subsets and the fixed development set.
- [x] MobileNetV2-256 learning curve is complete and reviewed: AP/AP50/AP75 improve monotonically
  through the full 312-row subset, while localization remains weak.
- [x] MobileNetV2-I320 comparison is justified by the 256 result and prepared against identical
  locked subsets; it completed and outperformed 256 on AP/AP50/AP75.
- [x] Development-only AppHear matching/threshold evaluator is implemented and smoke-tested for
  the 256 latency control and I320 accuracy candidate.
- [x] Both full-data candidates completed the locked 88-frame development threshold comparison.
- [x] I320 is the development winner but failed screening availability/two-hand/edge/IoU gates;
  C0-B0 promotion is no-go.
- [ ] A separately approved data/architecture decision exists before any detector retraining.
- [ ] QAT/INT8 and locked P0/N0/P1 evaluation remain blocked because the float development gate
  failed.

No RGB recognizer, fusion model, feature schema, production asset, or Android integration is ready.


