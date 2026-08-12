# Rollback And Compatibility Plan

**Purpose:** Guarantee that recognition research cannot strand or silently alter the working app.
**Status:** MANDATORY CONTRACT. **Last updated:** 2026-07-25.

## Protected Baseline

- Git recovery: tag `stable-baseline-before-redesign`, commit
  `67afa5f0815e758c32878282d87b3f00b2bdbb19`.
- Current production contract remains `schema_version=3.0`, `[1,96,258]`, 236 classes.
- Preserve current Android assets and all `_backup_*` asset directories.
- Preserve ASL Citizen/raw recorder videos, derived v3.0 features, run folders, configs, and audits.

## Isolation Rules

Use a dedicated branch; new directories such as `derived/.../hybrid_v0/`,
`runs/hybrid_*`, and `artifacts/recognition_upgrade/<experiment_id>/`; unique Android filenames
such as `hybrid_landmark.tflite`, `hybrid_rgb.tflite`, `hybrid_fusion.tflite`,
`hybrid_manifest.json`; experimental schema and vocab; one default-off feature flag. The runtime
must refuse schema/hash/shape mismatch and fall back to v3.0 without crashing.

## Compatibility

No adapter may pretend `hybrid.v0` is 258 or feed hybrid outputs to current S7 without an explicit,
tested acceptance adapter. UI consumes the same high-level idle/signing/committed state only after
shadow-mode parity. Old models never read new features; new models never overwrite old assets.

## Rollback Triggers

Any failed accuracy, class regression, calibration, false-positive, export, crash/ANR, p95,
thermal, battery, schema-parity, or device gate. Rollback is flag off plus restoration of the
baseline asset package; no database/data migration is required.

## Verification

After rollback run `testDebugUnitTest`, `assembleDebug`, S4 skew tests, and
`context/device-smoke.md`. Verify model/vocab/config hashes and controlled signs.

## Decisions, Assumptions, Risks, Open Questions, Next Action

- **Decision:** fallback is packaged and tested before any opt-in rollout.
- **Assumption:** APK size can temporarily carry both model families; measure in RU5.
- **Risk:** backup drift or shared mutable config.
- **Open question:** whether models ship in base APK or optional asset pack.
- **Next action:** no implementation until a baseline hash manifest is approved.


## Document Control

- **Scope:** Planning and experiment governance only; no implementation or production replacement is authorized.
- **Verified project references / source-of-truth files:** `CURRENT_PIPELINE_AUDIT.md`, `../feature-schema.md`, `../eval-protocol.md`, `../recognition-accuracy.md`, runtime Kotlin and Android assets named in the audit, and offline `pipeline/`, `model/`, `eval/`, and `artifacts/splits.json`.
- **Related context files:** `README.md`, `ARCHITECTURE_DECISIONS.md`, `EXPERIMENT_MATRIX.md`, `EVALUATION_AND_ACCEPTANCE_GATES.md`, `ROLLBACK_AND_COMPATIBILITY_PLAN.md`, and parent `../progress-tracker.md`.
- **Architecture decisions:** ADR-RU-001 through ADR-RU-016 apply; component-specific decisions in this document apply only after their experiment gate passes.
- **Assumptions:** Any forecast or unmeasured dimension remains a hypothesis, not a project fact.
- **Open questions:** Unresolved items are tracked in this document and `OPEN_QUESTIONS.md`.
- **Risks:** Applicable failure modes and fallbacks are tracked in this document and `RISK_REGISTER.md`.
- **Next required action:** Follow the explicit next action above and the ordering in `EXPERIMENT_MATRIX.md`; do not skip gates.

## Dynamic Mixed Rollback Addendum - 2026-07-31

The dynamic mixed architecture adds these compatibility rules:

- The primary model, confusion registry, calibration file, and any specialist resolver are separate assets with separate hashes.
- If the registry is missing or mismatched, the experimental recognizer must disable routing and fall back to the protected primary behavior or the production v3.0 recognizer.
- If a specialist resolver fails to load, exceeds latency budget, has a schema/group mismatch, or produces low confidence, the runtime must reject the hard sign rather than commit the primary guess.
- Disabling the experimental feature flag must restore the current production recognizer without requiring data migration.

## C0-B0 Isolation Addendum - 2026-08-09

- C0-B0 may create only new manifests, annotations, environments, and artifacts under its own
  experiment paths.
- Frozen P0/N0/P1 fixtures are read-only evaluation inputs and must never be copied into training.
- No detector asset may be placed in the Android application during C0-B0.
- A failed data, export, accuracy, quantization, or cost gate deletes nothing and changes no
  production fallback state.
- The rollback target remains the exact baseline recorded by `E6_0_BASELINE_FREEZE.md`.
- `c0b_toolchain_smoke_03/export/model.tflite` is a wiring artifact only and must never be copied,
  renamed, or referenced as an Android production asset.
- MediaPipe proposal boxes in annotation pilots are mutable review aids, not a replacement for
  frozen human gold or an input-contract change.

## Phase 1 Full-Vocabulary Isolation - 2026-08-11

- Phase 1 writes only under `artifacts/recognition_upgrade/phase1_full_vocab/` and uniquely named
  Phase 1 model directories.
- It reads production v3.0 assets as controls and never overwrites them.
- No Phase 1 output may enter Android assets, vocabulary, or configuration without a separately
  approved export/device phase.
- Any lineage, leakage, class-coverage, hash, reproducibility, or protected-test violation stops
  before training; the protected baseline remains untouched.

## Phase 1 Shadow Rollback - 2026-08-12

- The checked-in configuration keeps `phase1_shadow.enabled=false`; release
  `BuildConfig.PHASE1_SHADOW_ENABLED` is hard-coded false.
- The opt-in debug build uses `-Pphase1Shadow=true`; it does not alter the checked-in flag.
- Candidate assets use `phase1_shadow_*` names and never replace `streaming.tflite`,
  `model_manifest.json`, or `vocab.json`.
- Runtime loading verifies schema, dimensions, non-commit flags, vocabulary hash, and every model
  hash before constructing interpreters.
- Exact rollback is an ordinary build without `-Pphase1Shadow=true`; no dataset, confirmation,
  sentence, UI, or production-model migration is involved.
- Roll back on load/hash failure, crash/ANR, any UI/sentence effect, unacceptable FPS/latency or
  thermal impact, or evidence that shadow logging materially changes active timing.
