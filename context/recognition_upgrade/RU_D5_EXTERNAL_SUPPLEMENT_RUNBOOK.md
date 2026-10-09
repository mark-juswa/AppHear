# RU-D5 Targeted External-Signer Supplementation

Date: 2026-08-13  
Status: metadata audit complete; targeted source acquisition is the next developer-run step.

## Scope

RU-D5 constructs an isolated candidate C from the RU-D3 clean foundation plus
manually verified, MediaPipe-compatible external training-split clips for only
KNOW, WHO, WE/COME, and LEAVE. It does not modify RU-D3, train a model, access
the AppHear protected test, use the current phone signer, or change S5/S7,
schema v3.0 `[96,258]`, architecture, calibration, or Android.

## Verified source audit

- PopSign v1 is smartphone-recorded and signer-disjoint, but its official
  vocabulary contains WHO and WE/US—not KNOW, COME, or LEAVE. Because WE has no
  same-source COME partner, the only eligible PopSign download in RU-D5 is
  `game/train/who.tar`. PopSign validation/test archives are prohibited.
- Sem-Lex is the preferred next source for KNOW, WHO, and paired WE/COME. Its
  release requires the user to accept the dataset terms before receiving video
  links. Native validation/test signers remain excluded from AppHear training.
- MS-ASL official metadata contains training candidates for all targets: KNOW
  28 clips/22 signer IDs, WHO 33/28, WE 22/18, COME 6/5, and LEAVE 11/8. Only
  one training signer ID has both WE and COME, so MS-ASL cannot supply the
  desired five-signer paired pilot by itself. Its unconstrained/scraped domain
  requires strict manual and decode review.
- ASLLVD metadata exposes exact boundaries and lexical variants: 7 exact KNOW
  tokens, 2 WHO, 11 COME tokens across explicit variants, and 4 LEAVE tokens;
  it has no exact WE entry. It is a strong variant/boundary reference but not a
  standalone signer-diversity solution.

The frozen metadata audit is at
`artifacts/recognition_upgrade/ru_d5/external_candidate_01/`:

- `source_availability.csv`
- `candidate_discovery.csv`
- `screening_policy.json`
- `metadata_audit_summary.json`

It reports zero downloaded videos, zero extracted features, and zero accepted
training rows. Candidate C does not exist yet and training remains unauthorized.

## Acquisition optimization update

The former full PopSign WHO command is **deferred and must not be run**. The
minimal acquisition decision is now recorded in
`RU_D5_MINIMAL_ACQUISITION_MATRIX.md`.

PopSign's documented API makes the 2.71-GiB WHO tar the smallest supported
archive, but its public train filenames and HTTP byte-range support may allow us
to fetch ten selected members (roughly 45-60 MB) after preview review. Validate
that path first. Sem-Lex access/metadata inspection precedes all other target
downloads. MS-ASL remains row-selective by source timestamp. No full public
dataset download is currently approved.

## Deferred full-archive command

The official PopSign WHO training archive is `2,904,832,000` bytes. The command
below is retained only as a fallback and requires an explicit approval switch:

```powershell
Set-Location -LiteralPath 'F:\ASL DATASET\5. Apphear3'
& '.\model\config\recognition_upgrade\run_ru_d5_acquire_popsign_who.ps1' -ApproveFullArchive
```

Do not run it now. If later approved, the launcher downloads/resumes only
PopSign v1 `game/train/who.tar`, verifies
its exact byte size and SHA-256, extracts it under the isolated RU-D5 inbound
directory, counts decoded-file candidates, and reruns the metadata leakage
check. It does not download PopSign validation/test, run MediaPipe, review
variants, or add any training row.

Expected progress:

1. source/destination and expected-size banner;
2. resumable `curl` transfer progress for approximately 2.71 GiB;
3. archive SHA-256 calculation;
4. tar extraction and video-file count;
5. RU-D5 metadata check with `passed: true`;
6. final `RU-D5 POPSIGN WHO ACQUISITION COMPLETE` line.

Expected new files:

- `artifacts/recognition_upgrade/ru_d5/inbound/popsign_v1_0/game/train/who.tar`
- extracted WHO files under the neighboring `who/` directory

Rerunning is safe: a partial transfer resumes; a size-verified final archive is
not downloaded again; an existing extraction directory is not overwritten.

## Sem-Lex access boundary

Open `https://github.com/leekezar/SemLex` and follow its dataset terms link.
This consent-gated action cannot be automated on the user's behalf. Do not
download the entire Sem-Lex corpus yet: the current F: drive has about 13 GiB
free, and RU-D5 needs only four labels. After access is granted, report the
available archive/file listing or targeted-download options. If a targeted
archive has already been obtained, preserve its filename and native split
metadata and report its local path. The native structure will then be audited
before a Sem-Lex adapter or any video extraction is authorized.

## Later screening gate

Every downloaded clip remains `PENDING` until manual exact-variant and boundary
review passes. Only then may the existing MediaPipe IMAGE-mode Stage E, D1/D2,
and exact schema-v3.0 Stage F path run. The initial selector maximizes unique
eligible training signers before taking a second clip; WE and COME must be a
same-source/same-signer pair; alternate variants, missing required hands,
invalid spans, and weak landmark coverage are excluded rather than padded.

RU-D5 stops again after candidate C and the before/after report are complete;
no controlled retraining begins automatically.
