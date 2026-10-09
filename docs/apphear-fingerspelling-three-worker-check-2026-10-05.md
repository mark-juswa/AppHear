# Moderate additional PC use — three-worker check

Date: 2026-10-05T15:09:51.816174+00:00

## Decision: KEEP_VALIDATED_TWO_WORKERS

User asked to increase PC utilization while retaining normal PC responsiveness. A separate,
opt-in three-worker profile was implemented and tested; the running two-worker job was
not stopped or modified. The three-worker profile is NOT cleared for bulk use: its real
speed gate refuses startup because it showed no benefit in this bounded comparison.
Do not increase workers further or change Candidate01 thread settings to force a gain.

## Existing resource evidence

Ryzen5 5600G, 12 logical processors. A short active two-worker sample used approximately
19.7% of total CPU combined, approximately 1.1 GiB working set, with 12.13 GiB RAM available.
This short sample is not a maximum/typical-load guarantee.

## Tested safeguard and result

Three workers, each BELOW_NORMAL priority, restricted to the same eight available logical
CPUs; at least four logical CPUs excluded from worker execution. Minimum free RAM6GiB
at preflight; no model/thread/preprocessing changes. Affinity is logical CPU reservation,
not a guarantee of four idle physical cores or zero disk contention. No hard memory cap.
Both tested conditions used the same eight-CPU set and low priority. Worker diagnostics
verified actual affinity masks (8 CPUs) and priority class0x4000 for every completed clip.

Six existing TRAIN clips, 3–6second duration, three independent signers per stratum,
DAUN and MacKenzie. Selection followed frozen metadata order without looking at model
performance. Only new local fixture copies were extracted; no downloads or TEST payloads.

| Condition | Wall time for six clips |
|---|---:|
| Two workers | 56.666s |
| Three workers | 59.090s |

Three-worker speedup ratio: 0.959x, approximately4.3% slower, not a gain.
Includes cold worker startup/extraction/features/shutdown, excludes subsequent validation.
The existing I: two-worker job continued during both conditions. This is a bounded shared-
PC measurement, not proof that three workers are always slower or that hardware has hit
its maximum. It provides no justification for using more resources for this user run.
No speculative cause (CPU, disk, cache, model startup) is asserted.

All numeric raw-v1/feature arrays were byte-identical between two/three workers and original
foundation artifacts for all six clips. Both fixture packages passed structural/scoped
validation. Three distinct worker PIDs and overlap were observed; affinity/priority passed.
Gate failure is solely measured speedup, not perception quality or a broken implementation.

## Preservation / checks

Existing two-worker source/config/smoke identity and real gate still pass unchanged.
Original serial runner and frozen Candidate01/Adapter identities remain unchanged.
No WORD, Android, Context Assist, weights, dataset selection, or training changes.
No I: mutation by this task. No active preparation process was stopped or retuned.
32 focused preparation tests passed (14 original scheduler,12 external regression,6 new).
Mypy passed all three new files. Ruff passed with E501 excluded; one long metadata report
string remains a minor style finding in the bounded smoke script. No data-contract drift.

## New files / evidence

- `tools/fingerspelling/prepare_expansion_three.py`: guarded alternative scheduler; reuses
  existing extraction, source integrity, shared root lease, recovery and manifest helpers.
- `pipeline/config/fingerspelling_three_worker_execution_v1.json`: immutable three-worker
  CPU/RAM/priority/validation profile. Separate execution/parallel3 identity; old profile intact.
- `tools/fingerspelling/three_worker_preparation_smoke.py`: isolated six-clip gate.
- `tests/test_fingerspelling_three_worker_preparation.py`: CPU reservation/RAM guard,
  maximum in-flight writers/failure handling/gate checks.
- Evidence: `artifacts/fingerspelling_three_worker_preparation_01/parallel_smoke.json`,
  `tests.junit.xml`, `preservation.json`, `review.json`.
- Fixture data: `F:\ASL DATASET\5. Apphear3\.codex_tmp\three_worker_smoke_20261005_230454`. Original data unchanged.

Continue the CURRENT TWO-WORKER JOB. No switch-over or restart command is recommended.
The new profile must remain blocked; do not bypass the speed gate or silently repin it.

KEEP_VALIDATED_TWO_WORKERS
