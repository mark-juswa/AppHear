# E4-Q Confusion Resolver Package

**Purpose:** Define the focused resolver experiment for the E4-P `SORRY` collapse against `BECOME` and related `HELP` confusion before expanding the vocabulary again.

**Scope:** Research/experiment package only. This does not authorize Android integration, TFLite export, production recognizer replacement, source dataset mutation, or large vocabulary training.

**Current status:** Prepared, smoke-tested, and structurally checked on 2026-07-31. Full training is user-run.

**Verified project references:**

- Runner: `pipeline/rgb/e4_q_confusion_resolver.py`
- Run directory: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01`
- Config: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01/pilot_config.json`
- Manifest: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01/pilot_manifest.csv`
- Smoke summary: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01/smoke/smoke_summary.json`
- Check report: `artifacts/recognition_upgrade/e4_generalization/e4_q_confusion_resolver_sorry_become_help_01/check_report.json`
- Preceding pressure test: `context/recognition_upgrade/E4_P_EXISTING_FEATURE_20SIGN_PACKAGE.md`

## Why This Experiment Exists

E4-P showed that broad 20-sign expansion is not ready. The most important failure was not global collapse; it was a specific high-risk confusion:

- `SORRY` test performance collapsed in the 20-class context.
- The strongest repeated wrong mapping was `SORRY -> BECOME`.
- `HELP` also appeared in the `SORRY` error group.

The project decision is therefore to test a dynamic recognizer design: keep the global landmark model for stable signs, but add a specialist resolver for known hard confusion groups before accepting or committing those signs.

## Prepared Dataset

Classes:

- `GOOD`
- `SORRY`
- `HELP`
- `BECOME`

Prepared rows:

- Total active rows: `219`
- Train/validation/test: `108 / 26 / 85`
- Base tensor shape: `[96,258]`
- Derived tensor shape: `[96,728]`
- Schema version: `3.0`

Class counts:

| Split | GOOD | SORRY | HELP | BECOME |
|---|---:|---:|---:|---:|
| Train | 15 | 15 | 52 | 26 |
| Validation | 5 | 5 | 10 | 6 |
| Test | 30 | 30 | 13 | 12 |

Source counts:

- `local_core_e4j`: `100`
- `local_recorded_features`: `60`
- `asl_citizen_train`: `26`
- `asl_citizen_val`: `8`
- `asl_citizen_test`: `25`

Important limitation: `HELP` and `BECOME` test rows are ASL Citizen only in this prepared package. There is no local held-out `HELP/BECOME` coverage in the existing local feature tensor. This means E4-Q can answer whether a focused resolver improves the known landmark confusion, but it is not enough by itself to prove production readiness.

## Variants

| Variant | Input | Training | Purpose |
|---|---|---|---|
| `base_conv1d` | `[96,258]` | Standard | Control using the existing production-style feature representation |
| `derived_conv1d` | `[96,728]` | Standard | Tests whether velocity, acceleration, and relation features help separate similar signs |
| `derived_balanced_conv1d` | `[96,728]` | Class-weighted | Tests whether class imbalance is worsening the confusion |

Derived feature layout:

- Base v3.0 landmarks: `258`
- Velocity channels: `225`
- Acceleration channels: `225`
- Relations/presence features: `20`
- Total: `728`

## Gate

The resolver is promising only if it satisfies the written gate:

- Mean latest test accuracy >= `0.85`
- Minimum `SORRY` latest test accuracy >= `0.85`
- Minimum core latest test accuracy >= `0.85`
- Minimum candidate latest test accuracy >= `0.70`
- Maximum predicted-class share <= `0.45`

If the resolver passes, the next step is not Android export. The next step is parity/skew planning for the derived feature schema and then a source-balanced larger resolver validation.

If the resolver fails, the next high-value path is not more epochs. The fallback is either RGB hand/chest crop evidence for this confusion group or targeted data/label repair for `SORRY`, `HELP`, and `BECOME`.

## Smoke And Check Result

Smoke passed:

- `base_conv1d`: forward output `[12,4]`, one train batch completed, weights saved
- `derived_conv1d`: forward output `[12,4]`, one train batch completed, weights saved
- `derived_balanced_conv1d`: forward output `[12,4]`, one train batch completed, weights saved

Structural check passed:

- `check_report.json` reported `passed: true`
- No missing required prepared artifacts were reported

## User-Run Commands

Run full training:

```powershell
cd "F:\ASL DATASET\5. Apphear3"

.\.venv\Scripts\python.exe -m pipeline.rgb.e4_q_confusion_resolver run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_q_confusion_resolver_sorry_become_help_01"
```

Resume if interrupted:

```powershell
cd "F:\ASL DATASET\5. Apphear3"

.\.venv\Scripts\python.exe -m pipeline.rgb.e4_q_confusion_resolver run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_q_confusion_resolver_sorry_become_help_01" `
  --resume
```

Final check:

```powershell
cd "F:\ASL DATASET\5. Apphear3"

.\.venv\Scripts\python.exe -m pipeline.rgb.e4_q_confusion_resolver check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_q_confusion_resolver_sorry_become_help_01" `
  --require-metrics
```

## Source-Of-Truth Files

- Current production feature contract: `context/feature-schema.md`
- Upgrade feature strategy: `context/recognition_upgrade/FEATURE_SCHEMA_PLAN.md`
- Experiment ordering: `context/recognition_upgrade/EXPERIMENT_MATRIX.md`
- Acceptance gates: `context/recognition_upgrade/EVALUATION_AND_ACCEPTANCE_GATES.md`
- Rollback rules: `context/recognition_upgrade/ROLLBACK_AND_COMPATIBILITY_PLAN.md`

## Architecture Decisions

- E4-Q is a resolver experiment, not a replacement global recognizer.
- The existing `[96,258]` representation remains the control.
- The `[96,728]` derived representation is experiment-only until parity and Android feasibility are proven.
- Specialist confusion-group routing is allowed only after the global model first identifies a high-risk confusion set and the resolver provides calibrated separation.

## Assumptions

- Existing `HELP` and `BECOME` labels in ASL Citizen/local feature tensors are usable enough for a resolver probe.
- The E4-P confusion is meaningful enough to justify focused resolver testing before another large expansion.
- Three seeds are sufficient for the first resolver decision, but not for production release.

## Open Questions

- Can `SORRY` be separated from `BECOME` using landmarks plus derived temporal/relationship features only?
- Does class weighting help or just overfit the small resolver set?
- Are local held-out `HELP/BECOME` videos required before the resolver can be considered production-relevant?
- If landmark-derived features help, what is the smallest runtime-safe feature subset?

## Risks

- Source imbalance may make `HELP/BECOME` look better than they are on local phone recordings.
- Derived features may improve offline accuracy while introducing train/serve skew unless Kotlin parity is implemented carefully.
- A specialist resolver can reduce one confusion group but increase false accepts if not calibrated.
- A 4-class resolver can look strong while the global 20+ class recognizer remains weak.

## Next Required Action

The developer runs E4-Q full training and final check. After metrics are available, analyze per-class confusion, source-aware accuracy, variant winner, and gate result before preparing any further vocabulary expansion or RGB crop fallback.

**Last updated:** 2026-07-31.
