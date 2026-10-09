# FSBOARD_ADMISSION_DOWNLOAD_PREP

Prepared 2026-10-02 (Asia/Manila). **Metadata-only; 0 RGB downloads, 0 Candidate01 runs.**
AZ-0, AZ-1 and the completed [FSboard gate](fsboard-compatibility-gate-2026-10-02.md)
remain governing. The decision is still `FSBOARD_COMPATIBLE_WITH_LIMITS`. This package is a
TRAIN diagnostic inventory, not admitted training data or evidence of accuracy.

## 1. Repository state — VERIFIED

- Branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
- HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Protected WORD baseline: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`, via
  `baseline/apphear-s2-r2-integration-complete-2026-09-26`,
  `codex/recognition-stable-ru-d10` and the peeled
  `apphear-s2-r2-integration-complete-2026-09-26` tag.
- Starting worktree was dirty: modified `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`,
  `context/feature-schema.md`, `context/progress-tracker.md`, `memory.md`; untracked `.codex_tmp/`,
  AZ-0/AZ-1/FSboard reports, `context/fingerspelling-dataset-v1.md`,
  `context/recognition_upgrade/a1_signing_sentinel_01.csv`, `datasets/`, four `phone_pull*` directories,
  AZ policy/validator files and `tests/test_fingerspelling_dataset.py`. All are preserved.
- No material state drift from the gate. All 1,749 starting file hashes matched before handoff
  additions; subsequently only append-only handoffs were authorized in memory/progress/feature-schema.
  The existing 883-file protected snapshot has zero mismatches. No reset, merge, checkout, staging
  or commit; no Android, model, perception, word pipeline, Context Assist or release changes.
- Gate report, cached official view/list/license, metadata, four prior TRAIN diagnostic sources,
  raw outputs, receipts and evidence remain under
  `datasets/fingerspelling/fsboard_gate_20261002/`. The earlier four clip filenames are excluded
  uniformly, without consulting their Candidate01 results. No prior video/raw is inspected here.

## 2. Exact metadata/version — VERIFIED

Official dataset: [googleai/fsboard](https://www.kaggle.com/datasets/googleai/fsboard),
**v13**, release creation `2025-07-26T00:46:31.077Z` in the already cached official view.
Only these previously downloaded JSONs were opened for selection:

| Metadata relative to the gate's `official/` directory | Rows | SHA-256 |
|---|---:|---|
| `daun_v3/metadata/daun_v3-train.json` | 70,699 | `f85cbf264a4bab08924f5c19c565d3e9b32d4161fabe3004adeb40dd1ba56cdc` |
| `dmk_v3/metadata/dmk_v3-train.json` | 55,504 | `fcabb89d682fbc31af1427d120c7c228ac6a4cebe69cbf2b5b6d793a1782f4fc` |

They contain 8,906 DAUN and 55,504 MacKenzie eligible alphabet/space strings. Hash mismatches
stop regeneration. No new API calls, RGB, landmarks, Arrow, DEV or TEST payload access.

## 3. Selection method — IMPLEMENTED, reproducible

Policy: `tools/fsboard_admission/selection_policy.json`; generator:
`tools/fsboard_admission/prepare_manifest.py`. Use the full ASCII `[A-Za-z ]+` filter with at least
one letter; normalize by uppercase only, retaining spaces. No punctuation stripping or invented bounds.

There are **12 predefined slots**: two duration tails within three transcript-length bands for each
of two strata. Bands use the observed TRAIN metadata distributions and include spaces:
DAUN 3–11 / 12–15 / 16–31; MacKenzie 16–25 / 26–32 / 33–43. MacKenzie has no eligible transcripts
below 16 characters, so “shorter” is stratum-relative. Within each band, select from durations at
or below the nearest-index 25th percentile, or at/above the 75th percentile. Duration means
`clipEndTimeS - clipStartTimeS`; it is not decoded duration or a verified signing-speed label.

The slots require J, Z, MM, LL, EE and a no-J/Z/no-repeat control **in each stratum**.
Sort eligible candidates by SHA-256 of a fixed salt plus exact Kaggle relative path; break ties by
path. Take the first candidate with a previously unused official signer ID, full-video provenance key,
normalized phrase and source MD5, in the recorded slot order. No visual ease, hand success, file-size
ranking or inferred collection conditions influence selection. Candidate counts, thresholds, policy,
source hashes and complete official metadata rows are retained in JSON.

Twelve is the smallest sample under this six-cells-per-stratum design: it gives one clip for each
defined condition cell and cross-stratum transcript controls. It does not estimate corpus yield or
final model accuracy: selection is purposive, has one clip per signer, no held-out evaluation and
no visual quality labels. Any later failed clip stays inventoried; do not silently replace it with
an easier example.

## 4. Selected distribution and coverage — VERIFIED metadata

**12 distinct official TRAIN signer IDs; 6 DAUN + 6 MacKenzie; 12 distinct full-video provenance keys.**
The official collection IDs are `dpan-addresses-urls-numbers` and `dpan-mackenzie` (six each).
These are source collections, not twelve confirmed physical collection sessions. Official IDs and roles
are retained without reassignment or new human enrollment.

| # | Stratum | Signer | Transcript | Characters | Metadata seconds | Required slot |
|---|---|---|---|---:|---:|---|
| 1 | DAUN | 1d72 | jade hughes | 11 | 3.989 | shorter/lower/J |
| 2 | DAUN | d69c | surprise az | 11 | 6.027 | shorter/upper/Z |
| 3 | DAUN | 917d | sommer stevens | 14 | 3.996 | middle/lower/MM |
| 4 | DAUN | 740f | rochelle velez | 14 | 6.018 | middle/upper/LL |
| 5 | DAUN | d3ab | octavio hamilton | 16 | 3.008 | longer/lower/control |
| 6 | DAUN | c7d4 | kimberlee hammond | 17 | 7.988 | longer/upper/EE |
| 7 | MacKenzie | 6f68 | love means many things | 22 | 5.012 | shorter/lower/control |
| 8 | MacKenzie | 03ad | communicate through email | 25 | 7.998 | shorter/upper/MM |
| 9 | MacKenzie | 4f1e | just like it says on the can | 28 | 4.995 | middle/lower/J |
| 10 | MacKenzie | 9d2b | an excellent way to communicate | 31 | 10.037 | middle/upper/LL |
| 11 | MacKenzie | fe96 | labor unions know how to organize | 33 | 7.034 | longer/lower/Z |
| 12 | MacKenzie | 1f91 | shivering is one way to keep warm | 33 | 10.990 | longer/upper/EE |

Actual overlapping coverage: J **2** clips, Z **3**, repeats **6**; LL **2**, MM **4**, EE **2**;
controls **2**. Counts mean adjacent equal letters in transcripts, not verified separate visible
occurrences. Full J/Z motion is not established. DAUN rows appear to include name/place strings;
those semantics are an interpretation, not an official per-row category field. MacKenzie supplies
ordinary common phrases. Selected durations total **77.093 metadata seconds**.

One selected d69c clip shares the earlier diagnostic's full-video provenance, but is a different,
previously unselected MP4. No earlier perception result informed its selection. Twelve signer IDs
are the official identity evidence; this task does not independently reidentify humans or resolve
cross-project historical identity overlap.

## 5. Download package — READY, videos pending

**12 files, 97,918,150 expected bytes = 97.92 MB / 93.38 MiB.**

Destination (empty, created for convenience):
`F:/ASL DATASET/5. Apphear3/datasets/fingerspelling/fsboard_candidate01_admission_20261002/videos/`

Package files:

- [CSV manifest](../datasets/fingerspelling/fsboard_candidate01_admission_20261002/fsboard_candidate01_admission_download_manifest.csv)
- [JSON manifest](../datasets/fingerspelling/fsboard_candidate01_admission_20261002/fsboard_candidate01_admission_download_manifest.json)
- [Manual download sheet](../datasets/fingerspelling/fsboard_candidate01_admission_20261002/DOWNLOAD_SHEET.md)
- [Preparation checks](../datasets/fingerspelling/fsboard_candidate01_admission_20261002/PREPARATION_CHECKS.json)

Every row includes a stable `fsboard-v13-train-<path-identity-hash>` sample ID, exact original filename,
relative Kaggle path, original/uppercase transcript, official signer/collection, original full-video
provenance and timestamps, clip bounds/creation time, expected bytes/MD5, repeat flags and selection
reason. Full metadata is preserved in JSON; CSV flattens the essential fields. Unknown values are
JSON null / empty CSV fields. Clip creation time is not claimed as physical recording date.

The sheet contains all twelve per-file v13 URLs using the earlier verified API pattern; **none was
invoked**. Selected endpoint responses have not been tested. If Kaggle requires login, use the browser;
do not bypass authentication or rename HTML/ZIP responses to MP4. Use the official file browser and
version 13 if necessary. Download only these exact originals, without transcoding/renaming/mirroring.
File-size sums exclude HTTP overhead. No download-all operation is needed.

## 6. Offline integrity procedure — IMPLEMENTED and checked

From the repository, after downloading:

```powershell
.venv/Scripts/python.exe tools/fsboard_admission/verify_downloads.py --manifest "datasets/fingerspelling/fsboard_candidate01_admission_20261002/fsboard_candidate01_admission_download_manifest.json" --sha256 --report "datasets/fingerspelling/fsboard_candidate01_admission_20261002/download-integrity-result.json"
```

Optional `--videos-dir` overrides the destination. Checker uses Python standard library only and
has no network/decoder/perception imports. It checks schema/v13/TRAIN/path/stable identity, official
metadata linkage, JSON–CSV agreement, duplicate selected identities/signers/MD5s, required filenames,
actual byte sizes/MD5s, duplicate downloaded content, directory escapes and unexpected extra files.
Optional SHA-256 is computed locally in the same streaming read and linked to sample/manifest identity.
Exit 0 = complete file-integrity pass; exit 1 = missing/mismatched inventory; exit 2 = unreadable package.

Verification: **10 synthetic-byte tests PASS; Ruff PASS; scoped mypy PASS; in-process Black
formatting comparison PASS on all three Python files.** Regeneration produces
identical JSON, CSV and sheet hashes. Empty-destination dry run correctly reports exactly twelve
missing files, zero extras and no manifest/CSV errors; this is not a successful download check.
Black wrote formatted outputs but CLI completion stalled on both initial and single-worker attempts;
those processes were interrupted after `/recover` isolated the failure to formatter CLI execution.
The in-process formatting comparison completes normally, without worker/cache writes. The CLI stall's
precise cause remains unknown; Black CLI pass is not claimed.

## 7. Unresolved evidence and stop boundary

Metadata lacks resolution, FPS, saved rotation/reflection, physical session/device conditions and
per-letter boundaries. These were not fabricated or inferred from earlier clips. Decode, original
orientation/reflection, full transcript completeness and frozen Candidate01 coverage remain for the
next authorized admission check. The binary checker cannot settle them. Existing FSboard gate limits,
future common-input parity, phone cadence, sequence governance and negative/rejection coverage remain.

No architecture change: frozen Candidate01 → raw-v1/common phone evidence → future parity-tested
adapter → sequence encoder → character CTC → spelled text. No extraction, training, feature adapter,
runtime mode, word commit, Context Assist or release change. **Stop and wait for the user to download
the twelve files and explicitly confirm readiness.**

FSBOARD_DOWNLOAD_MANIFEST_READY
