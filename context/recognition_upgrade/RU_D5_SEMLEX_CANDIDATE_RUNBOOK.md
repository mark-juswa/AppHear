# RU-D5 Sem-Lex Targeted Repair Candidate

Date: 2026-08-14  
Status: first video scan preserved 38/40 selected videos; targeted missing-member audit and valid-
row pose extraction are the next developer-run step. Candidate C does not exist yet.

## Prepared selection

The immutable pre-screening manifest is:

`artifacts/recognition_upgrade/ru_d5/semlex_candidate_01/semlex_screening_manifest.csv`

It contains 40 Sem-Lex TRAIN rows and no validation/test rows:

| Class | Rows selected | New signers | Selection note |
|---|---:|---:|---|
| KNOW | 10 | 5 | two per signer; all ASL-LEX metadata matches head/forehead one-hand family |
| WHO | 10 | 5 | two per signer; all ASL-LEX metadata matches head/chin one-hand family |
| WE | 5 | 4 | balanced with COME over the same four signer IDs |
| COME | 5 | 4 | balanced with WE over the same four signer IDs |
| LEAVE | 10 | 5 | two per signer; intended symmetric/two-hand family prioritized |

The exact WE/COME overlap is Sem-Lex signers `39`, `49`, `80`, and `84`. Three paired signer
groups have ASL-LEX evidence on both sides. Signer 84 WE, signer 49 COME, and one LEAVE row are
freetext candidates with missing phonological metadata; they are intentionally marked
`UNKNOWN_REVIEW_REQUIRED` and receive no acceptance credit without video review.

This is a screening set, not a training quota. Every row remains `PENDING`.

## Selective extraction command

Run from PowerShell:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\model\config\recognition_upgrade\run_ru_d5_semlex_selective_extract.ps1'
```

The command streams `D:\Downloads\train.tar.gz` and
`D:\Downloads\sem-lex-train-poses.tar.gz` once each. It writes only the 40 selected `.webm`
members and their 40 matching `.npy` pose files into the isolated RU-D5 directory. It never
unpacks either complete archive and never downloads anything.

Because gzip-compressed tar files do not provide random member access, the command may need to
read most of both 23.67-GB and 8.27-GB archives even though it writes only selected files. This is
the unavoidable long-running part; the developer runs and observes it.

Expected progress:

1. `RU-D5 SEM-LEX SELECTIVE EXTRACTION` safety banner;
2. video archive progress every 5,000 members plus one line per selected video found;
3. pose archive progress every 5,000 members plus one line per selected pose found;
4. JSON summary with `videos_extracted: 40`, `poses_extracted: 40`, `passed: true`;
5. post-extraction hash validation with `errors: []`, `passed: true`;
6. final `RU-D5 SEM-LEX SELECTIVE EXTRACTION COMPLETE` line.

Successful initial completion creates:

- `inbound/videos/*.webm` (40 selected files only);
- `inbound/provided_poses/*.npy` (40 matching files only);
- `selective_extraction_manifest.csv` with video and pose SHA-256 hashes;
- `selective_extraction_summary.json`;
- `pre_screen_check.json`.

The launcher is resumable without overwriting selected files. A wrong-size existing member stops
the run instead of replacing it.

## What happens after extraction

Stop and return the final console output. The next agent-run step is short inspection of the
provided `.npy` layout followed by a five-video exact-pair pose probe. AppHear Stage E will be run
on the same five videos to compare frame count/alignment, landmark order, handedness, coordinates,
visibility, and missing-hand semantics. Supplied poses remain ineligible for Candidate C unless
that equivalence is proved.

After the pose probe, all 40 videos receive bounded visual variant/boundary/framing review. Only
manual passes proceed through the existing AppHear MediaPipe IMAGE-mode Stage E, D1/D2, and exact
schema-v3.0 `[96,258]` Stage F path. The final build must prove RU-D3 hashes unchanged, validation
unchanged, no test materialization, and every unrelated vocabulary row byte-identical.

No MediaPipe extraction, manual acceptance, Candidate C assembly, retraining, PopSign/MS-ASL,
TODAY, S5/S7, feature-schema, architecture, specialist, or Android work is authorized by this
prepared step.

## Partial video-scan recovery — 2026-08-14

The first video scan reached archive EOF and preserved 38 selected files before reporting two
missing canonical members:

| Video ID | Class | Signer | Role | Current decision |
|---|---|---|---|---|
| `V5XMcoCE0a8XrK5nELEr` | COME | `SEMLEX-80` | COME half of the signer-80 WE/COME pair | canonical member missing; no other Sem-Lex TRAIN COME row exists for signer 80 |
| `puu6X6CTG4oUkQmcj3o5` | LEAVE | `SEMLEX-84` | second LEAVE clip for signer 84 | canonical member missing; no replacement needed because signer 84 remains represented |

The preserved distribution is KNOW 10/5 signers, WHO 10/5, WE 5/4, COME 4/3, and LEAVE 9/5.
Only WE/COME pairing is weakened: pair-eligible rows are four WE plus four COME across signers
39, 49, and 84. Signer-80 WE remains an unpaired diagnostic row and cannot enter training alone.

The canonical paths were absent after the complete first archive traversal. Proving that neither
basename exists under a different directory, extension, or case requires one name-only traversal
of the compressed video tar. The recovery launcher searches only those two stems; it does not
re-extract or rehash the other video members from the archive. It then scans the pose archive only
for video-valid rows.

Run:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\model\config\recognition_upgrade\run_ru_d5_semlex_missing_audit_and_poses.ps1'
```

Expected behavior:

1. preserve and reuse all 38 existing video files;
2. scan video archive names for only the two missing basenames across path/extension/case;
3. mark no-match rows `ARCHIVE_MEMBER_MISSING`, or recover the original ID if exactly one
   alternate member exists;
4. skip the ordinary video extraction pass;
5. extract matching supplied pose files only for rows with a valid video;
6. hash-check every valid video/pose pair and stop before pose equivalence or MediaPipe.

The missing-member audit is complete. Do not run either archive launcher again.

## Visual and supplied-pose screening checkpoint

The two absent video rows are finalized as `ARCHIVE_VIDEO_MISSING`. The missing supplied pose
for `XRGDr8F4tCHv6uQNwaPd` is nonfatal by itself, but bounded visual review independently found
that the preserved VP9 video returns zero decoded frames, so that clip is `UNUSABLE`.

A five-clip matched probe across KNOW, WHO, paired WE/COME, and LEAVE established:

- video and supplied-pose frame counts match for all five clips;
- Sem-Lex uses `(T,553,3)` float16 arrays with empirical
  `FACE478_POSE33_LEFT21_RIGHT21` ordering;
- the arrays do not contain AppHear's pose visibility, hand score, or pose score contract;
- missing-hand coverage is not consistently equal to AppHear's canonical extractor.

Therefore supplied Sem-Lex poses are rejected for direct schema-v3.0 feature generation. Raw
videos must pass through AppHear's canonical extraction path.

Bounded filmstrip review produced 34 visually eligible clips: KNOW 6, WHO 10, WE 5, COME 4,
and LEAVE 9. Three KNOW clips are wrong variants. WE-80 is visually eligible but remains
WE/COME pair-ineligible and cannot enter training alone.

Run the canonical AppHear extraction manually:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\model\config\recognition_upgrade\run_ru_d5_semlex_apphear_extract.ps1'
```

The launcher is resumable and processes only the 34 visually eligible videos. It runs the
existing MediaPipe Stage-E extractor, frozen offline training D1/D2 span detector, and
schema-v3.0 Stage-F builder. This is the Phase-1/RU-D3 training-data contract; it does not invoke
Android runtime S5. If D1/D2 cannot find a valid span on a visually reviewed isolated clip of
6-96 frames, the runner preserves a full-clip Stage-F fallback marked provisional and requiring
manual boundary confirmation. A valid D1/D2 span that fails landmark quality is not rescued by
this fallback. EXACT_TARGET and ACCEPTABLE_VARIANT remain separate: acceptable variants are
extracted for evidence only and cannot enter Candidate C automatically, with particular caution
for WE/COME. The launcher validates every emitted `[96,258]` tensor and hash. It does not read
either archive, accept a training row, build Candidate C, or train.

## Final bounded failure review and COME replacement

Raw-frame plus Stage-E hand-overlay review classified the 15 unavailable features as 12
boundary-only failures, two already-provisional variant rows, and one genuine MediaPipe-domain
failure. The 12 failed exact rows received explicit visually bounded spans, and the provisional
WHO fallback received a manually confirmed span. All 13 rebuilt features pass the unchanged
class-specific landmark gates. The exact pool before replacements is KNOW 6/4 signers, WHO 9/5,
WE 4/3, COME 2/2, and LEAVE 7/5. Only COME still needs a final diversity screen.

The final replacement manifest contains five unused Sem-Lex TRAIN ASL-LEX COME rows, one each
from signers 11, 31, 38, 85, and 88. Run:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\model\config\recognition_upgrade\run_ru_d5_semlex_final_replacements.ps1'
```

This streams the local TRAIN video archive once for only those five members and creates bounded
filmstrips. It does not read the supplied pose archive, run MediaPipe, accept rows, build
Candidate C, or train. Paste the result back before final visual/AppHear screening.
