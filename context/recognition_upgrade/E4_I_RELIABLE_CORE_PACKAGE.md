# E4-I Reliable-Core 4-Sign Package

**Purpose:** Stop trying to rescue weak local signs and prepare a clean benchmark using only local signs with the strongest current evidence.

**Scope:** Experiment package only. This does not authorize Android integration, model export, production-recognizer replacement, feature-schema promotion, source-video mutation, or dataset deletion.

**Current status:** Prepared, smoke-tested, and structurally checked. Full training is not started.

**Last updated:** 2026-07-30.

## Verified Project References

- Package script: `F:\ASL DATASET\5. Apphear3\pipeline\rgb\e4_i_reliable_core.py`
- Source run: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_f_cleaned_diagnostic_pilot_01`
- E4-I package: `F:\ASL DATASET\5. Apphear3\artifacts\recognition_upgrade\e4_generalization\e4_i_reliable_core_4sign_pilot_01`
- Dataset tensor: `dataset\landmark_features.npz`
- Candidate decision report: `logs\candidate_decision_report.csv`
- Runbook: `README_RUN.md`
- Smoke summary: `smoke\smoke_summary.json`
- Check report: `check_report.json`

## Why This Replaces The Review Loop

E4-F and E4-G already showed that `BYE` and `NO` are not reliable in the current local data/model path:

- `BYE`: E4-F test `0/29`; E4-G `BYE -> YES` collapse `28/29`.
- `NO`: E4-F test `12/30`; E4-G `NO -> YES` confusion `17/30`.
- `THANKYOU`: partly label/variant-confounded; E4-F only `10/17`.

The project should not keep spending time reviewing these weak signs before proving a smaller stable core.

## Selected Reliable-Core Signs

| Gloss | Reason | E4-F selected TCN seed303 held-out result |
|---|---|---:|
| `GOOD` | Three-signer local support; strong held-out behavior | `29/30`, `0.9667` |
| `HELLO` | Three-signer local support; strong held-out behavior | `28/30`, `0.9333` |
| `SORRY` | Three-signer local support; strong held-out behavior | `29/30`, `0.9667` |
| `YES` | Three-signer local support; strong held-out behavior | `25/28`, `0.8929` |

Excluded from this core:

| Gloss | Reason |
|---|---|
| `BYE` | Bad current evidence; collapses into `YES` |
| `NO` | Unstable current evidence; often collapses into `YES` |
| `THANKYOU` | Label/variant issue and weak cleaned result |

## Dataset

E4-I reuses the cleaned E4-F `[96,258]` tensor. No MediaPipe extraction is rerun.

- Active rows: `238`
- Excluded rows: `176`
- Split counts: train `90`, validation `30`, test `118`
- Classes: `GOOD`, `HELLO`, `SORRY`, `YES`

Class counts:

| Split | GOOD | HELLO | SORRY | YES |
|---|---:|---:|---:|---:|
| Train | 15 | 45 | 15 | 15 |
| Validation | 5 | 15 | 5 | 5 |
| Test | 30 | 30 | 30 | 28 |

Known limitation: train/validation class balance is not perfect because this package reuses available cleaned rows. This is acceptable for a reliable-core diagnostic, but any production dataset still needs broader signer and class balance.

## Validation Completed

Smoke test passed:

- Input shape: `[8,96,258]`
- Conv1D forward output: `[8,4]`
- Masked TCN forward output: `[8,4]`
- One training batch ran for both branches.
- Smoke weights were saved.

Structural check passed:

```json
{
  "passed": true,
  "errors": []
}
```

## User Training Command

This is the long step and should be run by the user:

```powershell
cd "F:\ASL DATASET\5. Apphear3"
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_i_reliable_core run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_i_reliable_core_4sign_pilot_01"
```

Resume if interrupted:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_i_reliable_core run `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_i_reliable_core_4sign_pilot_01" `
  --resume
```

Check after training:

```powershell
.\.venv\Scripts\python.exe -m pipeline.rgb.e4_i_reliable_core check `
  --run-dir "artifacts\recognition_upgrade\e4_generalization\e4_i_reliable_core_4sign_pilot_01" `
  --require-full-dataset `
  --require-metrics
```

## Gate

Go only if:

- validation-selected mean held-out test accuracy is at least `0.85`,
- every selected class is at least `0.80` on held-out test,
- no predicted-class collapse appears,
- masked TCN is at least competitive with Conv1D after validation selection.

No-go if:

- any selected class falls below `0.80`,
- train/validation are near-perfect but held-out test drops sharply,
- predictions collapse into one or two classes.

## Decision After E4-I

If E4-I passes, the next practical move is to expand around this reliable core by adding only signs that have enough clean, signer-disjoint support.

Local two-signer candidates that need another signer before production-grade signer-independent use:

- `GET`
- `MAKE`
- `WELCOME2`
- `HAVE`
- `KNOW`
- `GO`

ASL Citizen/E3 candidate-keep signs from the previous audit are separate-provenance candidates, not direct local replacements:

- `SWITZERLAND`
- `COUCH`
- `CURLYHAIR`
- `DOWNSIZE1`

Do not mix local Stage-E and ASL Citizen evidence in one production claim without a new explicit split/provenance plan.

## Next Required Action

User runs E4-I training and check. Do not run E4-H review, another full 7-sign benchmark, Android integration, or production export before E4-I is evaluated.
