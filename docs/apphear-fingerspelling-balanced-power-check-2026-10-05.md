# Additional PC power — warmed balanced three-worker check

Date: 2026-10-05T15:38:19.381486+00:00

## Decision: KEEP_VALIDATED_TWO_WORKERS

User explicitly asked for more preparation power without making the PC unusable. The
current two-worker I: run was left unchanged. No bulk job was started or stopped by agent.

Initial PC sample: approximately44.8% overall CPU and11.49GiB free RAM. Two existing worker
processes remain BELOW_NORMAL. A separate candidate uses three workers, restricted to
ten of twelve logical CPUs, leaving two excluded from worker execution, with BELOW_NORMAL
priority and at least6GiB available RAM required at preflight. This is logical CPU affinity,
not two guaranteed idle physical cores, not a memory limit, and not a whole-system CPU cap.

The earlier eight-CPU/cold three-worker gate remained preserved. This follow-up addresses
user's request using a modestly greater CPU set and warm sustained-work timing. It does
not alter Candidate01 defaults/models/math or the405-column/raw-v1 contracts.

## Controlled bounded evidence

Same six TRAIN source identities as the preceding gate, three signers per DAUN/MacKenzie
stratum; original source copies only. No downloads, TEST, dataset changes, model training,
WORD or Android changes. Both measured conditions used the same ten-CPU restriction.

Each unchanged Candidate01 initialized once and processed one real warm-up frame before
timing. A barrier verified all workers ready. The same six full originals were then acquired
from existing copies, hash-verified, extracted and transformed. New fixtures are under:
`F:\ASL DATASET\5. Apphear3\.codex_tmp\balanced_smoke_20261005_233153`. Startup/shutdown/scoped validation excluded from warm timings;
startup itself measured6.666s/two and6.858s/three. This is not a recognition-accuracy test.

| Condition | Warm six-clip time | Whole-PC mean CPU during timed work |
|---|---:|---:|
| Two workers | 51.901s | 73.28% |
| Three workers | 51.038s | 93.33% |

Throughput ratio1.01693x: only1.7% higher throughput (~0.864s saved across six clips).
This is too small to establish a meaningful speed benefit from higher utilization.
Whole-PC CPU was measured through Windows GetSystemTimes. The user's two-worker job
continued during BOTH benchmark conditions: the means therefore include that job and
other applications. They are NOT standalone two/three-worker CPU estimates. No claim
that a three-worker production job alone would use93% is justified. Conversely, the
small observed gain does not justify recommending a switch under the requested headroom.
No cause of throughput saturation is asserted without profiling (memory/disk/cache/etc.).

All masks/time/raw numeric arrays and native/sparse feature arrays matched two-versus-three
and original foundation arrays byte-for-byte (dtype/shape included). Both fixture packages
passed structural validation with zero scoped pending. Three worker PIDs overlapped;
every worker reported ten-CPU affinity and actual BELOW_NORMAL priority. Receipt/package
locations and timing fields legitimately differ. No interpolated/fabricated observations.

## Safety / approval consequence

The measured automatic gate marks a mathematically positive speed ratio, but that does
not mean operational promotion is justified. A separate explicit execution approval is
FALSE, and the candidate CLI refuses preparation before any acquisition or extraction.
This prevents accidentally treating a noisy1.7% gain as a cleared higher-power workflow.
Do not bypass the gate or flip approval flags. No more worker/timing sweep is authorized.

Benchmarked source copies in `benchmarked_source/` match the immutable identity recorded
in `parallel_smoke.json`. After measurement, only an additional default-deny execution
approval guard was added. Candidate extraction/affinity functions remained unchanged.
The original two-worker module/config/gate remains untouched and passes its original gate.
The running I: frozen serial/Adapter identity also matches. Preservation evidence:
`preservation.json`. This task made no I: writes and did not kill/retune user processes.

One Windows benchmark bootstrap error was corrected: multiprocessing Event must be shared
through initializer inheritance, not a task queue. The isolated failed fixture/log remains
preserved; the corrected bounded benchmark passed. No Candidate01 adjustment was made.

## Tests / new artifacts

39 focused scheduler/external preparation tests passed after the approval guard; Ruff and
Mypy passed the three new implementation/test files. Focused checks cover CPU reservation,
RAM guard, capped dispatch/failure handling, unchanged two-worker socket ownership/resume/
idle validation, explicit rejection of an unapproved candidate. No train/serve skew added.

New files:
- `tools/fingerspelling/prepare_expansion_balanced.py`: separate guarded scheduling candidate.
- `pipeline/config/fingerspelling_balanced_execution_v1.json`: three/ten-CPU low-priority policy.
- `tools/fingerspelling/balanced_preparation_smoke.py`: warm bounded byte-parity timing test.
- `tests/test_fingerspelling_balanced_preparation.py`: focused safety tests.
- Evidence: `artifacts/fingerspelling_balanced_preparation_01/parallel_smoke.json`,
  `execution_approval.json` (false), `preservation.json`, `tests.final.junit.xml`, `review.json`,
  benchmarked-source archive and new local fixture outputs.

Continue the EXISTING TWO-WORKER COMMAND. No stop/switch/restart needed. Current validated
preparation remains resumable, data remains I:, completed work remains retained, and F:
foundation/model/Android/protected WORD state remains unchanged.

KEEP_VALIDATED_TWO_WORKERS
