# APPHEAR_FINGERSPELLING_TRAINING_FOUNDATION_01

2026-10-02. **Offline research foundation validated; actual first-tranche preparation pending.**
The user selected: “Build and validate the foundation now; freeze the 1,024/256 manifest and
batch commands for later acquisition.” Therefore this milestone deliberately prepares features
for the existing 12 TRAIN clips and freezes the larger manifest. It does not claim that a
12-TRAIN / 0-DEV package is ready to train. No new video acquisition, Candidate01 inference,
model training, Android modification or TEST payload access occurred.

## 1. Repository state — VERIFIED

- Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
- HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Protected WORD baseline: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`, including
  `baseline/apphear-s2-r2-integration-complete-2026-09-26` and recognition-stable baseline refs.
- Existing modified files: `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`,
  `context/feature-schema.md`, `context/progress-tracker.md`, `memory.md`. Their contents were
  preserved; only the latter three receive append-only AppHear foundation notes.
- Existing untracked work includes AZ-0/AZ-1/FSboard documents, dataset/tool/validator files,
  signing-sentinel evidence, `.codex_tmp/` and `phone_pull_*` directories. No reset, branch
  switch, merge, stage, commit or cleanup was performed.
- Preservation evidence: `datasets/fingerspelling/foundation_01/preservation.json`; initial
  snapshot includes 2,082 existing identities outside the intentionally appended documents.
  Original 12-clip manifest SHA remains
  `23f1bf347f016f3ffe208d4dc181038c1d814a00c4c340c0dc669b0db9bcd000`.

AZ-0, AZ-1, the compatibility gate, admission closure, phone follow-up and reflection report
remain unchanged historical evidence. The **new user research decision** supersedes reflection
admission restrictions for this baseline only; it does not revise their earlier findings.

## 2. Feature contract and exact order — FROZEN

`FingerspellingFeatureAdapter.v1` is variable `[T,405]` float32. There is no fixed T/window,
future-dependent normalization or reuse of WORD features. Full semantics:
[`context/fingerspelling-sequence-v1.md`](../context/fingerspelling-sequence-v1.md).

| Zero-based columns | Layout |
|---|---|
| 0–1 | dt_seconds, dt_valid |
| 2–169 | slot 0, joints 0..20 × eight joint fields |
| 170–182 | slot 0, thirteen extra fields |
| 183–350 | slot 1, joints 0..20 × eight joint fields |
| 351–363 | slot 1, thirteen extra fields |
| 364–403 | body indices 5,6,7,8,9,10,11,12 × five body fields |
| 404 | upstream body_available flag |

Joint fields: source_x/y, local_x/y, source_valid, local_valid, proposal_support, support_valid.
Extras: presence, presence_valid, observed, proposal_present, roi_x/y/side, roi_valid,
palm_scale, scale_valid, wrist_dx/dy, motion_valid.
Body fields: source_x/y, support, xy_valid, support_valid.

Source geometry divides by upright width/height. Hand shape is wrist-relative and divided by
the current mean wrist-to-MCP distance over joints 5/9/13/17, valid only when all five points
are observed/valid and scale exceeds short_side × 1e-6. Invalid local scale leaves valid source
XY intact. No handedness canonicalization or reflection is performed.

All conditional geometry has explicit masks and zero invalid values. Finite support/presence
is distinct from hand acceptance. No forward fill or search backward across missing hands.
Wrist displacement uses adjacent selected observations, equal source dimensions and gap ≤1 s;
it describes a slot, **not a tracked physical hand**. Duplicate/overlapping slots stay separate.
Each valid body point is retained independently of body_available; a full torso is unnecessary.

Pinned identities:

| Identity | SHA-256 |
|---|---|
| adapter Python implementation | `256d8e82301fa9e6dd039a1c6d94dc5cc717b22c27e7b8bd9661ba32ee4394cd` |
| feature config | `5ed7f766154b558ea2bebd095804ca788dc7ee5b91cc001ca96a40133edb9b67` |
| newline-joined ordered column names | `f3f5f93cd590111e60a1078c032ada7a756be72d633ff53900ae9a353f084fcb` |

## 3. Python/Android-compatible semantics — VERIFIED SCOPE

All inputs map to existing `PhoneRawObservation` fields in `PhoneCausalCore.kt`: timestamp,
upright size, XY, joint-valid, proposal support, presence, observed, proposal-present, ROI,
body XY/support/valid/available. No Python handedness, Z/world, labels, split/signers,
profiling or word outputs are features. Absolute timestamp is lineage; only dt enters the model.

Python implementation: `pipeline/fingerspelling/adapter.py`.
Unused JVM reference: `tools/fingerspelling/FoundationParity.kt`, **outside Android source sets**.
The serialization contains only shared observation fields. Android code/build configuration
and the production camera path were not changed.

`parity/parity.json` verifies 10 fixture observations and all 12 real clips in native and phone
views: 2,766 real observations, **1,124,280 float32 values total**, bit-for-bit equal on this host.
Tolerance contract remains atol/rtol 1e-6; do not generalize host bit equality to all devices.
Fixture cases cover normal evidence, one/both missing slots, duplicate slots, partial validity,
absent body, non-finite scores/ROI, missing wrist, consecutive motion, large gap and resolution
change. Synthetic fixtures are explicitly marked not training data.

**Still future:** port/wiring to actual Android observation objects, on-device parity and timing.
The JVM result proves reference arithmetic, not installed Android adapter/deployment behavior.

## 4. Sequence data contract — FROZEN

The new manifest/artifact/receipt schemas are `apphear.fingerspelling.sequence_manifest.v1`,
`apphear.fingerspelling.sequence_features.v1` and `apphear.fingerspelling.sequence_receipt.v1`.
Old AZ-1 interval/OTHER contracts and their validator remain intact.

Targets are A..Z (indices 0..25), SPACE (26). CTC blank is logit/loss/decoder index 27, never
a transcript character. Normalize entire ASCII alphabet/space transcripts by uppercase only,
without stripping or collapsing spaces. Repeats include adjacent repeated spaces.
No OTHER character, letter boundaries, manual character timing or transition relabeling.

Rows retain official role, signer, stratum, collection/full-video identity, transcript,
normalized transcript, official source metadata, exact v13 path/size/MD5, and deterministic
source-based ID. Receipts add source/raw/raw-receipt/feature SHA-256s and paths, manifest identity,
adapter/config/order identity, timestamps, lengths, repeats and CTC feasibility statuses.
NPZs retain actual features/timestamps/frame indices/targets, embedded feature masks, upstream
native masks and genuine selected phone-view indices/timestamps/features.

No source metadata or labels enter model columns. CTC length is actual encoder output length;
this foundation assumes an unstrided future encoder for readiness, not a fixed temporal window.

## 5. Reflection research policy — AUTHORIZED LIMITATION

`reflection_policy = USE_RELEASED_PIXELS_AS_IS`

`reflection_provenance = STRONGLY_SUPPORTED_UNMIRRORED_NOT_FULLY_ATTRIBUTED`

The three exact-clip unmirrored findings remain verified; the other nine exact-clip findings
remain UNKNOWN. No collection-wide formal proof is claimed. No source or feature is flipped.
New research receipts/manifest authority permit reuse of the unchanged diagnostic raw cache;
prior `training_admitted=false` receipts remain immutable rather than being rewritten.
Publisher inquiry remains separate and unsent; it no longer blocks this research phase.

## 6. DEV/TEST governance — FROZEN BEFORE MODEL SELECTION

Official TRAIN/validation/TEST human roles remain unchanged and signer-disjoint. MacKenzie has
official TRAIN only; no synthetic MacKenzie DEV or TEST is created.

Deterministic policy: exclude DEV sequences whose uppercase, whitespace-preserving normalized
phrase occurs in eligible official TEST **metadata**. This excludes **981 DEV rows over 465
distinct phrases**, leaving **1,371 DEV rows across all 15 DEV signers**. TEST is not changed
and its RGB/raw/features are not opened. Exclusion IDs and official metadata hashes are frozen
in `dev_phrase_policy.json`, SHA
`e029b1e2fb698ce53d810adf0d475d28697bd8394450876e2308c759dabdbb28`.
TRAIN has no normalized-phrase overlap with these other eligible official roles in the prior
metadata audit. This lexical separation is additional to official signer separation.

## 7. Controlled tranche — METADATA SELECTED, NOT YET EXTRACTED

Official `googleai/fsboard` version 13, already cached metadata only:

| Metadata | SHA-256 |
|---|---|
| DAUN TRAIN | `f85cbf264a4bab08924f5c19c565d3e9b32d4161fabe3004adeb40dd1ba56cdc` |
| MacKenzie TRAIN | `fcabb89d682fbc31af1427d120c7c228ac6a4cebe69cbf2b5b6d793a1782f4fc` |
| DAUN DEV | `d306aac4c80e7052492ebffdd01f2e8242d09755ff7243824e866360fb609648` |
| DAUN TEST metadata only | `94f53f6c9d9199cbc50c5207a31a96d400734e49eac60d4a157fc515a587423b` |

Selection: fixed SHA ordering within length/J/Z/repetition/ordinary buckets, signer round-robin,
512 per TRAIN stratum, 256 eligible DEV. All 12 prior clips are forced into TRAIN independently
of Candidate01 results. No difficult source is replaced; CTC capacity does not filter selection.
Class enrichment means this DEV tranche is a challenge subset, not an unbiased full-DEV sample.

| Metadata-selected inventory | TRAIN | DEV |
|---|---:|---:|
| sequences | 1,024 | 256 |
| official signers | 117 | 15 |
| DAUN / MacKenzie | 512 / 512 | 256 / 0 |
| sequences per signer, min–max | 5–14 | 17–18 |
| transcript characters, including spaces | 18,377 | 3,457 |
| transcript length min / median / max | 3 / 16 / 42 | 4 / 13 / 31 |
| J-containing sequences | 318 | 59 |
| Z-containing sequences | 270 | 52 |
| adjacent-repeat sequences | 425 | 109 |
| uniform phone-rate CTC bound failures, metadata estimate | 18 | 2 |
| source bytes | 7,053,025,841 | 1,578,716,662 |

All 27 transcript classes occur in each selected role. Exact frequency dictionaries and lengths
are in `tranche_manifest.json`; these are metadata statistics, not actual extracted coverage.
Q/X remain sparse, and source/phone domain differences remain limitations. This engineering
tranche tests feasibility across diverse signers; it guarantees no accuracy target or final
dataset sufficiency. Add later batches using learning-curve evidence without changing v1.

Frozen tranche manifest SHA:
`6b4f152c6bd51eae7af697a58c88c6e20cb0b5e537e272a1a84a897aec54ae6e`.

## 8. Extraction and training-manifest pipeline

`frozen manifest → bounded official RGB acquisition → expected size/MD5 + source SHA →
frozen Candidate01 decoder/preprocessing/models → chronological raw-v1 + extraction receipt
→ adapter v1 native and genuine sparse views → features + receipt → validation + CTC inventory`

The separate sequence wrapper calls frozen `iter_video_frames` and
`Candidate01Offline.process_rgb`; it does not call word ingest, the old 258 extractor, S2,
Recognition V2 or publisher landmarks. Existing bytes/receipts/features are reused first.
Candidate assets remain pinned to ONNX `37b0f265…` and hand refiner `6acda74a…`; full hashes
and four frozen preprocessing source hashes are enforced by the package validator.

`tools/fingerspelling/foundation.py` has separate metadata, reuse, validation, acquisition and
extraction commands; **no training command**. `batch_plan.json` freezes 80 bounded batches:
64 TRAIN + 16 DEV, max 16 sources each. Failed/partial sources stay pending for review; no
automatic relabeling or silent omission. Authentication/access failures must be surfaced.
No acquisition/extraction batch was executed in this phase; the first future batch is the
end-to-end check of the new wrapper before proceeding through the frozen plan.

From `F:\ASL DATASET\5. Apphear3`, a future explicitly requested first batch can use:

```powershell
.venv/Scripts/python.exe -m tools.fingerspelling.foundation plan-batch --role TRAIN --start 0 --count 16
.venv/Scripts/python.exe -m tools.fingerspelling.foundation acquire-batch --role TRAIN --start 0 --count 16
.venv/Scripts/python.exe -m tools.fingerspelling.foundation extract-batch --role TRAIN --start 0 --count 16
.venv/Scripts/python.exe -m tools.fingerspelling.foundation validate
```

Repeat with explicitly selected role/start/count from `batch_plan.json`; TEST is unavailable
to these commands. Destination: `datasets/fingerspelling/foundation_01/videos/`, `raw/`,
`features/`. Original diagnostic sources/raw remain in their prior folders. No auto-delete
of original RGB/raw is included; hashes alone do not substitute for retained audit sources.

## 9. Practicality — ESTIMATES, NOT GUARANTEES

Full tranche RGB: **8,631,742,503 bytes (~8.63 GB, 8.04 GiB)**; subtract ~97.9 MB of already
downloaded sources for new acquisition. Total metadata clip duration ~7,249.55 s.
Assuming ~30 source FPS gives ~217,486 native frames; uniform phone-rate estimate ~45,173.
At 405 float32 columns, native + sparse features take ~425.5 MB before masks/metadata/raw
caches, or compression. Actual 12 compressed feature archives total **1,904,620 bytes**.
Raw caches are additional; actual resolutions/FPS/storage are measured only after acquisition.

Prior 12 frozen extractions took 173.38 s over 2,292 frames: aggregate **13.22 frames/s** on
that host. Same-host, same-throughput, ~30-FPS extrapolation is **~4.57 extraction hours** for
the tranche, excluding download/model startup/validation and thermal/content differences.
This is host throughput, not phone cadence or future model inference latency.

## 10. Actual prepared dataset and CTC readiness — VERIFIED

Only the fixed 12 TRAIN raw outputs were converted. Sources again passed expected size/MD5,
SHA, raw and receipt identities. Previous Candidate01 extraction was reused, not rerun.

| Actual extracted/converted inventory | TRAIN | DEV |
|---|---:|---:|
| sequences / signers | 12 / 12 | 0 / 0 |
| DAUN / MacKenzie | 6 / 6 | 0 / 0 |
| transcript characters | 255 | 0 |
| native observations | 2,292 | 0 |
| genuine selected phone-view observations | 474 | 0 |
| native CTC feasible / infeasible | 12 / 0 | 0 / 0 |
| sparse phone-view CTC feasible / infeasible | 12 / 0 | 0 / 0 |
| J / Z / repeated sequences | 2 / 3 / 6 | 0 / 0 / 0 |

TRAIN clips span 11–33 transcript characters and 91–331 observations. Across frames, any-hand
observation rate is **73.47%**; missing-hand fraction per sequence ranges **7.25–71.90%**.
Full per-sequence distributions remain in feature receipts and `validation.json`. Missing
hand frames are retained as masked timesteps, not dropped or retargeted. F and Q are absent
from this tiny actual smoke; all classes occur in the selected but pending tranche.

Phone sensitivity view greedily selects actual observations separated by at least
1000/6.231166 ms and recomputes dt/motion. Discrete selection is conservative and does not
reproduce the measured phone's exact gaps, drops, image resolution or motion-information loss.
No intermediate evidence is fabricated. Metadata uniform estimates and actual sparse counts
are deliberately separate. For every sequence/view, `T >= target_length + adjacent_repeats`
is recorded; actual loss must use **encoder output** lengths. Stride changes require rechecking.
Passing this bound is not recognition accuracy, alignment quality or moving-letter proof.

## 11. Validation and review

Scoped verification: **69 tests passed, 5 subtests passed** across the new foundation suite,
existing AZ validator suite and existing FSboard download suite. Ruff passes for new code;
mypy passes five new source files with silent imported-module checking / missing-import
ignores. No broad WORD test/evaluation or Android build was needed for this offline scope.

Validator: **0 structural errors**, 12 validated sequences, 1,268 pending. It checks metadata
authority, schema/class/order identities, signer and copied-source isolation, no TEST source,
DEV phrase exclusion, source/raw/receipt/feature hashes, pinned Candidate01 lineage, masks,
timestamps, finite/deterministic output and exact CTC statuses. Tampering, schema mismatch,
partial geometry, chronology errors and network-free source reuse have regression tests.
`ctc_views.json` lists eligible/infeasible retained IDs explicitly. Readiness is never promoted
merely by a successful structural validation or by the existence of tooling.

Architect/review outcome: scope and system-integrity checks pass; no critical implementation
finding. Preparation remains incomplete by the user's acquisition deferral. Important limits
are pending actual TRAIN/DEV preparation, sparse rare-letter coverage, phone-domain/cadence
loss and future installed Android parity. The new batch wrapper is prepared but its first
new-video end-to-end run is pending. Production integration and release remain unauthorized.

## 12. Remaining work and recommendation

Next authorized development step can be **one bounded acquisition/extraction batch**, followed
by validation, then the remaining frozen TRAIN/DEV batches. Once the governed tranche and
eligible per-role character coverage pass, one later training run can use a causal TCN with
one output per observation and 28 character/blank logits. Use genuine sparse views for
phone-rate sensitivity, explicit CTC lengths, held-out-signer DEV and no language correction.
No architecture sweep, feature-width search or production change is proposed here.

Current blocker is the deferred **actual dataset preparation**, not historical reflection.
No usable DEV feature sequence exists yet. The 12 clips validate adapter/lineage plumbing;
they cannot answer generalization or final dataset-size questions. Stop before training.

FINGERSPELLING_BASELINE_PREPARATION_BLOCKED
