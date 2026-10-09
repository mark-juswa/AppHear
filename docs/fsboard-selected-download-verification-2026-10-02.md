# FSboard selected download verification

2026-10-02 (Asia/Manila). The user explicitly requested assistant downloading after the
manual-download preparation. That supersedes the manual-download restriction for the exact selected
files. This follow-up performs download and source-integrity checks only; it does not begin the
Candidate01 training-admission check.

- Branch remains `codex/current-working-text-to-asl-baseline-2026-09-29`;
  HEAD `cc1f3949114d0ed1dab38d4428191151b37df358`.
- Protected WORD baseline remains `76d93cecd85bf9f76064d320aa4a5791b5f0704a`;
  883 protected source/asset hashes match, zero mismatches. Unrelated dirty work preserved.
- Downloaded exactly **12 official FSboard v13 TRAIN MP4s**, six DAUN/six MacKenzie,
  **97,918,150 bytes (97.92 MB / 93.38 MiB)**. The sample selection is unchanged.
- Original files are in
  `F:/ASL DATASET/5. Apphear3/datasets/fingerspelling/fsboard_candidate01_admission_20261002/videos/`.
- Only manifest-listed per-file public URLs were retrieved. No credentials, protected TEST/DEV
  videos, landmarks, Arrow shards or full-corpus retrieval. Each source was finalized only after
  matching the official size and MD5; no transcoding or pixel transformations.
- Independent `tools/fsboard_admission/verify_downloads.py --sha256` passed all twelve sources:
  **0 errors, 0 unexpected files**, exact filename/manifest/CSV mapping, unique selected identities
  and downloaded content, matching sizes/MD5s. SHA-256 recorded for every source.
- Frozen manifest SHA-256 remains
  `23f1bf347f016f3ffe208d4dc181038c1d814a00c4c340c0dc669b0db9bcd000`.
  CSV and download-sheet hashes also match the preparation record. `git diff --check` passes.

Evidence under `datasets/fingerspelling/fsboard_candidate01_admission_20261002/`:

- `selected_download_retrieval.json`: exact retrieval identities, expected/actual bytes, MD5,
  SHA-256 and completion state. No redirected signed URLs or authentication material stored.
- `download-integrity-result.json`: independent checker result and all twelve source hashes.
- The earlier `PREPARATION_CHECKS.json` and `pre_download_integrity_check.json` remain historical
  preparation evidence, accurately showing the then-empty destination; do not overwrite them
  to imply videos existed during metadata-only selection.

The sample is ready for the next bounded Candidate01 admission check. **File integrity is verified;
video decode/completeness, orientation/reflection, perception coverage and training admission are
not assessed here.** No new raw-v1 extraction, model training, Android, Candidate01, WORD pipeline,
Context Assist or release changes. The earlier `FSBOARD_COMPATIBLE_WITH_LIMITS` decision remains.

FSBOARD_SELECTED_FILES_VERIFIED
