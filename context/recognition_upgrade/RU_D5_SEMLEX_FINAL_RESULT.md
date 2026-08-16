# RU-D5 Sem-Lex Final Result

**Status:** COMPLETE — Candidate C frozen; Sem-Lex curation stopped  
**Date:** 2026-08-14

## Final replacement pass

All five extracted replacement videos visually matched the frozen
`COME_INWARD_TO_TORSO_V1` target. The canonical AppHear Stage E -> offline D1/D2 -> Stage F path
accepted one automatic span. Four D1/D2 spans were reviewed against bounded filmstrips and the
frame-level hand trace:

- `40NUoGm2C3kglAnw1Mcw`: accepted with manual span `14..28`, any-hand coverage `0.8000`.
- `0m47KrzJpXjObEsBMXS6`: accepted with manual span `5..24`, coverage `0.5500`.
- `qSNUBz6BrfogcpPCdKFB`: accepted with manual span `17..32`, coverage `1.0000`.
- `mV7NXGseruwyLLVM5JeS`: automatic release `29` was visibly early; accepted with manual span
  `18..36`, coverage `0.7895`.
- `DGfGoi7GtNAe1i2FkC8u`: rejected `MEDIAPIPE_DOMAIN_FAILURE`; a hand remained visible during the
  sign, but MediaPipe detected only `8/22` frames in the D1/D2 interval (`0.3636`).

No landmark threshold was changed and no further replacement cycle is authorized.

## Frozen exact-target external pool

| Gloss | Clips | External signers | RU-D3 clips | Candidate C clips |
|---|---:|---:|---:|---:|
| KNOW | 6 | 4 | 27 | 33 |
| WHO | 9 | 5 | 6 | 15 |
| WE | 4 | 3 | 11 | 15 |
| COME | 6 | 6 | 11 | 17 |
| LEAVE | 7 | 5 | 8 | 15 |

WE/COME is no longer a one-sided repair: both have a bounded exact-target pool, and signers 39 and
49 provide same-signer pairs. COME has two more clips because the final pass prioritized recovery
from zero initially surviving exact rows; no questionable variant was added to force numeric
balance.

## Candidate C contract

Candidate C is the unchanged 3,820-row RU-D3 tensor followed by 32 Sem-Lex TRAIN exact-target
rows, for 3,852 total rows. Validation and vocabulary files are byte-identical to RU-D3. All
external rows are limited to KNOW, WHO, WE, COME, and LEAVE. `ACCEPTABLE_VARIANT` rows are excluded,
the current phone signer is absent, and no protected-test artifact was accessed or materialized.

Primary artifacts:

- `artifacts/recognition_upgrade/ru_d5/semlex_candidate_01/candidate_c/dataset/dataset_contract.json`
- `artifacts/recognition_upgrade/ru_d5/semlex_candidate_01/candidate_c/final_external_lineage.csv`
- `artifacts/recognition_upgrade/ru_d5/semlex_candidate_01/candidate_c/candidate_c_report.json`
- `artifacts/recognition_upgrade/ru_d5/semlex_candidate_01/replacement/apphear_extraction/final_extraction_manifest.csv`

Candidate C remains non-production and was not trained during RU-D5.
