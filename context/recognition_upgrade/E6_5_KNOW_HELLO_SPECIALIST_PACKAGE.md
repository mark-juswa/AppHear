# E6-5 KNOW/HELLO Specialist Package

**Purpose:** Record the implemented, isolated E6-5 package and the exact developer-run procedure.

**Scope:** Offline specialist experiment only. No Android, TFLite, RGB, fusion, routing,
production asset, raw dataset, or feature-contract change is authorized.

**Current status:** COMPLETE / STRUCTURAL PASS / RECOGNITION NO-GO. See `E6_5_KNOW_HELLO_SPECIALIST_RESULT.md`.

**Last updated:** 2026-08-09.

## Verified Project References

- Plan: `E6_5_KNOW_HELLO_SPECIALIST_PLAN.md`
- Runner: `pipeline/rgb/e6_5_know_hello_specialist.py`
- Tests: `tests/test_e6_5_know_hello_specialist.py`
- Run: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01`
- Pilot config: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01/pilot_config.json`
- Lineage: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01/source_lineage.json`
- Smoke: `artifacts/recognition_upgrade/e6_specialists/e6_5_know_hello_specialist_01/smoke/smoke_summary.json`

## Prepared Data

Both representations contain exactly the same rows and lineage:

| Split | HELLO | KNOW | Total |
|---|---:|---:|---:|
| Train | 163 | 90 | 253 |
| Validation | 34 | 31 | 65 |
| Variant stress | 60 | 30 | 90 |
| Fresh test | 60 | 60 | 120 |
| Historical test | 14 | 13 | 27 |

All five splits passed sample ID, participant ID, source ID, label, length, frame-mask, and base
channel alignment. Geometry's first 258 channels exactly match v3.0.

## Smoke Result

- v3 TCN specialist: copied `17` encoder layers; `[4,96,258] -> [4,96,2]`; one training step,
  save, reload, and finite-output checks passed.
- Geometry TCN specialist: copied `17` encoder layers; `[4,96,444] -> [4,96,2]`; one training
  step, save, reload, and finite-output checks passed.
- Frozen primary control: `[2,96,258] -> [2,96,5]` passed.
- Structural check with `--require-smoke`: passed with no errors.
- Focused E6-2/E6-4/E6-5 tests: `8 passed`.

TensorFlow's native-Windows GPU warning is expected on this machine and is not a package failure.

## Full Run

```powershell
cd "F:\ASL DATASET\5. Apphear3"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_5_know_hello_specialist train `
  --run-dir "artifacts\recognition_upgrade\e6_specialists\e6_5_know_hello_specialist_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_5_know_hello_specialist evaluate `
  --run-dir "artifacts\recognition_upgrade\e6_specialists\e6_5_know_hello_specialist_01"

.\.venv\Scripts\python.exe -m pipeline.rgb.e6_5_know_hello_specialist check `
  --run-dir "artifacts\recognition_upgrade\e6_specialists\e6_5_know_hello_specialist_01" `
  --require-smoke `
  --require-metrics
```

Resume only if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e6_5_know_hello_specialist train `
  --run-dir "artifacts\recognition_upgrade\e6_specialists\e6_5_know_hello_specialist_01" `
  --resume
```

The run trains six small models: two branches times three seeds. It does not repeat extraction.

## Outputs

- checkpoints: `models/<branch>/seed_<seed>/`
- histories: alongside each seed's checkpoints
- aggregate result: `metrics/metrics.json`
- structural validation: `check_report.json`

## Architecture Decisions

- The fixed evaluation policy is `latest.keras`; `best` and `final` are diagnostic.
- The future router remains the frozen v3 five-way primary; E6-5 does not implement it.
- RGB is excluded because the closest AppHear RGB specialist and fusion experiments failed.
- Geometry must clear a complexity gate over v3, not merely tie it.

## Assumptions, Risks, And Open Questions

- **Assumption:** the existing source-scoped participant IDs represent real distinct signers.
- **Risk:** fresh and stress signers have already influenced architecture decisions, so a pass is
  provisional and requires a new untouched signer before production.
- **Risk:** train data remains concentrated in a few local recorder identities.
- **Open question:** can either specialist recover stress `KNOW` while preserving `HELLO` and
  historical ASL Citizen performance?

## Next Required Action

The run is complete. Follow `E6_5_KNOW_HELLO_SPECIALIST_RESULT.md` and
`E6_COMPONENT_DECISION.md`; do not begin E6-6, RGB work, export, or Android work.
