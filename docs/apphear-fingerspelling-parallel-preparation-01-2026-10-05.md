# AppHear fingerspelling — moderate two-worker preparation

Date: 2026-10-05T14:22:05.012267+00:00
Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.
Protected application baseline: `cee71d9f181695847936eb5f3605ea37eab82a95`.

## Decision

Offer an opt-in two-worker, BELOW_NORMAL-priority runner. The existing serial command,
frozen Candidate01 thread settings/models/preprocessing, raw-v1 and Adapter.v1 `[T,405]`
are unchanged. This is scheduling only, not an accuracy/model experiment.
No bulk preparation, downloads, training or Android changes were performed by the agent.
The user's serial job was left running throughout; it must be stopped before switching.

## Measured evidence

The Ryzen 5 5600G exposes 12 logical processors. A three-second serial sample used
approximately 15.4% total CPU and 647.6 MB working set. Available RAM was approximately
11.2 GiB of 27.9 GiB. These are samples, not an enforced CPU ceiling.

A bounded benchmark reused four existing TRAIN originals, two independent signers from
each DAUN/MacKenzie stratum, selected by frozen metadata order and 3–6-second durations.
No sources were selected using perception results. New copies/outputs are isolated in
`F:\ASL DATASET\5. Apphear3\.codex_tmp\parallel_smoke_20261005_221533`. Both conditions used BELOW_NORMAL priority and identical frozen
per-worker runtime settings, including the existing two-thread inference defaults.

| Condition | Workers | Four-clip elapsed seconds |
|---|---:|---:|
| Serial | 1 | 63.111 |
| Parallel | 2 | 43.005 |

Measured speedup: 1.468x (31.9% shorter elapsed time). Includes worker
startup/source checks/extraction/feature generation/shutdown, excludes the later scoped
validator. Both worker processing intervals overlapped. Numeric raw and feature arrays
(dtype, shape, every byte; including masks/time/phone views) matched serial versus
parallel AND original foundation artifacts for all four clips. Archive/receipt bytes need
not match: output locations, package hashes, ZIP timestamps and timing fields differ.
Both fixture packages passed existing structural/scoped validation with zero pending.
This small benchmark does not guarantee the same speedup on downloads/longer clips or
under other PC workloads. No throughput-related recognition-accuracy claim is made.

## Scheduling and recovery contract

- Fixed maximum two independent processes; one cached unchanged Candidate01 per process.
- Lower Windows process priority yields to ordinary foreground PC work. No hard CPU cap.
- Parent is the only execution-log/failure/progress writer; individual sample paths are unique.
- Same socket ownership port as serial runner. Worker-inherited socket retains the lease
  if coordinator dies; guardian exits workers after parent death. Both locks are tested.
- At most two clips in flight. No concurrent validation while another clip writes a pending
  feature NPZ: validate only at idle two-batch barriers, then full validation at the end.
- Resume starts with existing full source/raw/features validation, frozen hash checks and
  explicit quarantine of known manifest-owned unfinished stages. Committed data is reused.
- Ctrl+C stops dispatch, lets current worker clips settle, retains completed records. Failed
  identities remain explicit, stop new dispatch, and are retried by the same command.
- New runner/config/gate identity is stored separately under execution/parallel; no migration
  or overwrite of the serial implementation identity. The original serial runner remains
  the fallback after stopping parallel safely.
- Minimum available RAM 4 GiB and eight logical processors are preflight requirements.
- TRAIN/DEV manifest and batch plan remain identical; TEST remains sealed.

## Validation and preservation

26 focused tests passed: new scheduler/lock/inherited ownership/exception/interrupt/resume/
idle-barrier tests plus existing external preparation regression tests. Mypy passed three
new files. Ruff passed excluding E501; one smoke report string is 109 columns (minor style
finding; no behavioral defect). The Windows socket test requires unsandboxed local named-
pipe IPC; it passed outside the desktop sandbox. No restriction bypass in the user runner.

11,239 protected source/dataset/run/Android inventory hashes match the earlier
preservation snapshot; changed identities: 0. All four locked serial code
hashes and Adapter identity match the active I: implementation identity. A read-only
ownership probe confirmed the live serial job rejects a parallel writer. No TEST payload
is present in the hashed inventory (Android unit-test source files are not dataset TEST).

## Exact user handoff

In the current preparation terminal, press Ctrl+C ONCE and wait for the PowerShell prompt.
Do not launch a second writer while it is still active. Then paste:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion_parallel preflight --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
if ($LASTEXITCODE -eq 0) {
    & .\.venv\Scripts\python.exe -u -m tools.fingerspelling.prepare_expansion_parallel prepare --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
}
```

Full resume validation may take several minutes before extraction begins. The same prepare
command safely resumes subsequent stops. Do not edit model/config/hash identities.

Status, read-only:
```powershell
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion_parallel status --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
```
Final validation after completion:
```powershell
& .\.venv\Scripts\python.exe -m tools.fingerspelling.prepare_expansion_parallel validate --destination 'I:\AppHearData\FSboard_TRAIN4096_01'
```
Target: 3,072 additions + original 1,024 TRAIN = 4,096; separate DEV-B 256; DEV-A unchanged.
Progress/events/failures stay in the existing I: execution directory. New parallel profile
and batch reports live under execution/parallel. Existing F: foundation stays in place.
If the PC feels busy, Ctrl+C once, wait, then resume using the original serial command.

## Files / evidence

New implementation: `tools/fingerspelling/prepare_expansion_parallel.py`.
New bounded gate: `tools/fingerspelling/parallel_preparation_smoke.py`.
New opt-in config: `pipeline/config/fingerspelling_parallel_execution_v1.json`.
New tests: `tests/test_fingerspelling_parallel_preparation.py`.
Evidence directory: `artifacts/fingerspelling_parallel_preparation_01/`:
`parallel_smoke.json`, `tests.junit.xml`, `preservation.json`,
`handoff_preflight_readonly.json`, `review.json`.
Context registry/progress/memory appended; no older entries erased.

TWO_WORKER_PREPARATION_USER_RUN_READY
