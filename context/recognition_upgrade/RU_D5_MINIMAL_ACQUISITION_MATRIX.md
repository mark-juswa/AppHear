# RU-D5 Minimal External Acquisition Matrix

Date: 2026-08-13  
Status: acquisition decision complete; no large video archive downloaded.

## Decision

RU-D5 will optimize for the first **usable signer** rather than the first large
archive. One accepted clip per new signer is selected before any second clip,
except that WE/COME requires a same-signer pair and LEAVE may later take two
extra clips after five distinct signers. Every count below is an initial screen,
not an automatic training quota.

| Class | Preferred source | Exact AppHear variant status | New external signers needed | Initial clips to screen | Minimum download method | Estimated transfer/storage | Fallback |
|---|---|---|---:|---:|---|---|---|
| KNOW | Sem-Lex train, conditional on access | Not yet verified in released metadata/video; ASLLVD's seven exact one-hand KNOW tokens confirm the lexical family but do not prove Sem-Lex rows match | 3 | 6-9 from at least 3, preferably 6, train signers | Request/access metadata first; download individual train clips only if the release permits. Reject a full-corpus-only route. | Unknown until access; target tens of MB, not a corpus download | MS-ASL train: screen 8-10 timestamped clips from distinct signer IDs; roughly 40-150 MB including section-download overhead |
| WHO | PopSign v1 game/train | PopSign's reviewed game variant exists; equality to `WHO_ONE_HAND_FACE_CHIN_V1` remains manual-review pending | 5 | 10 clips: 2 from each of 5 signer prefixes, preview first | Official API minimum is the complete 2.71-GiB WHO tar. Prefer public preview adjudication followed by selected HTTP byte-range extraction of tar members; validate one member first. | About 45-60 MB for 10 originals based on the 2.71-GiB/526-clip archive mean, plus negligible tar-header indexing; worst case full tar 2.71 GiB | Sem-Lex train if per-clip access exists; then MS-ASL train 10-12 distinct-signer timestamp sections |
| WE / COME | Sem-Lex train, only if paired signer population is available | Neither exact AppHear path is verified until video review; both members of each pair must pass | 5 paired signers | 6-8 pairs (12-16 clips) to yield 5 accepted pairs | Filter native train metadata for signer IDs containing both labels; download only those paired clips | Unknown until access; target roughly 60-200 MB if per-clip | MS-ASL has only one train signer ID with both labels: screen that one pair as feasibility evidence, not as a complete repair. If Sem-Lex cannot provide five valid pairs, do not supplement WE alone. |
| LEAVE | Sem-Lex train if it exposes exact two-hand rows; otherwise screened MS-ASL train | Sem-Lex/MS-ASL unverified. ASLLVD has four metadata-confirmed exact two-hand LEAVE tokens (both hands open/B-or-5 to closed/A-or-flat-O), matching the intended family | 5 | 10-12 distinct-signer clips; accept at least 7 clips across 5 signers | Sem-Lex per-clip train download if available; otherwise timestamp-section download of the 11 MS-ASL train candidates across 8 signer IDs | Sem-Lex unknown; MS-ASL approximately 50-180 MB for the bounded screen | ASLLVD's four exact tokens may supplement only after distinct signer identity and practical clip-level acquisition are verified; otherwise keep them as variant/boundary references |

## Why these are the minimum signer targets

- KNOW already has 27 clean clips and ten total training signers, but only two
  local-domain signer IDs. Three external signers are the smallest meaningful
  diversity addition after RU-D4 showed ranking improvement without Top-1 rescue.
- WHO has six clean ASL rows and no target-domain coverage. Five external signers
  preserve the previously registered minimum without assuming repeat clips from
  one person replace diversity.
- WE is already healthy offline. Five WE/COME pairs are not a WE volume target;
  they are the minimum matched-domain test of the phone confusion.
- LEAVE has eight clean clips and lost Top-1 while staying Top-5. Seven accepted
  clips across five external signers restore nominal support without returning
  wrong-variant or missing-hand rows.

## Download granularity findings

### PopSign WHO

The documented PopSign API does not support individual original videos. Its
smallest official unit is the complete `game/train/who.tar`, exactly
`2,904,832,000` bytes. The archive contains 526 train clips from 31 signer
prefixes. The public WHO page exposes split-specific original filenames and
preview videos, and the archive server advertises HTTP byte ranges. A bounded
alternative is therefore possible:

1. visually review low-resolution previews from five train signer prefixes;
2. choose two likely exact-variant clips per signer;
3. remotely index tar headers (about 526 512-byte range reads);
4. retrieve only the ten selected member byte ranges;
5. verify each member name, size, and SHA-256 before review/extraction.

This is not a documented PopSign API feature, so one selected member must pass a
range-extraction/decode validation before the ten-clip transfer is approved. If
the server stops honoring byte ranges, the only supported fallback is the full
2.71-GiB tar; that download requires a separate user decision.

### Sem-Lex

The public repository exposes a terms form, not the native file listing. The
form requires attribution, non-commercial use, share-alike terms, and respectful
handling commitments. Until the user accepts those terms and sees the release,
we cannot truthfully claim target presence, exact variants, per-clip granularity,
or storage size. The correct next action is access/metadata inspection—not a
full download.

### MS-ASL

The official 1.9-MB metadata package is already audited. It references timestamp
sections in source videos, so acquisition can be row-selective rather than
corpus-wide. The bounded downloader should fetch only chosen train timestamps,
with short boundary buffers, then store the cut clip. Source availability and
license restrictions remain per-row risks. Validation/test rows and signers are
never fallback training data.

### ASLLVD

ASLLVD provides exact lexical labels and sign/clip frame boundaries. The bulk
site exposes batch archives rather than a documented per-clip API. Its four
exact two-handed LEAVE tokens are unusually strong variant evidence, but their
signer mapping and practical selective-download path must be verified before
calling them supplementation. No full ASLLVD batch is justified for RU-D5.

## Acquisition order

1. Submit/accept the Sem-Lex access form and inspect the provided file listing
   without downloading the corpus.
2. Build and validate one PopSign WHO tar-member range fetch; do not run the
   existing full-archive launcher.
3. Resolve Sem-Lex target and paired-signer availability. Select only native
   train rows.
4. Use MS-ASL row-level timestamp downloads only for gaps Sem-Lex cannot fill.
5. Use ASLLVD for adjudication; promote its LEAVE clips only if selective access
   and signer identity pass.

No video acquisition, MediaPipe extraction, candidate C assembly, or training is
authorized by this matrix.
