# NEGATIVE_GOLD_V1 External Open Images Package

**Date:** 2026-08-21  
**Status:** `OPEN_IMAGES_EXTERNAL_CANDIDATE_PACKAGE_FROZEN_UNREVIEWED`  
**Scope:** external RGB discovery and blinded-review preparation only

## Executive result

A bounded Open Images V7 validation package is frozen with 220 canonical images and 20 concealed, byte-identical repeats. No image has been labeled `ZERO_HAND`. The existing trusted benchmark remains 76/200 until human review and a separately executed QC/finalization phase.

| Measure | Frozen result |
|---|---:|
| Canonical candidates | 220 |
| Concealed exact repeats | 20 |
| Review rows | 240 |
| Person-free discovery category | 143 (65.0%) |
| People-present discovery category | 77 (35.0%) |
| Unique source landing pages | 220 |
| Unique authors | 219 |
| Unique metadata primary labels | 174 |
| Downloaded source bytes | 66,447,613 |
| Image dimension range | 557-1024 px wide; 393-1024 px high |

The discovery categories come only from Open Images human image-label metadata. They are hidden from the reviewer and are not hand-absence truth.

## Official source and access verification

- Dataset: [Open Images V7](https://storage.googleapis.com/openimages/web/index.html), current published version, released October 2022.
- Format and downloads: the [official V7 download page](https://storage.googleapis.com/openimages/web/download_v7.html) documents per-image metadata fields and a bounded image-ID downloader.
- Pixel mirror: the [CVDF Open Images mirror](https://github.com/cvdfoundation/open-images-dataset) exposes the validation images through the public `open-images-dataset` S3 bucket; individual objects were downloaded rather than the 12 GB validation archive.
- Annotation license: CC BY 4.0.
- Per-image license metadata: CC BY 2.0 for every retained candidate.

The official image metadata fields preserved here are `ImageID`, `Subset`, `OriginalURL`, `OriginalLandingURL`, `License`, `AuthorProfileURL`, `Author`, `Title`, `OriginalSize`, `OriginalMD5`, `Thumbnail300KURL`, and `Rotation`. The package adds official mirror URL, UTC download timestamp, SHA-256, dHash, decoded dimensions, and internal selection lineage.

Open Images states that it makes no warranty about each image's license status. This package therefore records complete attribution metadata but does not represent a legal guarantee. Before public redistribution or product use, re-check the original landing page and any privacy, publicity, or moral-rights constraints.

CC BY attribution requires appropriate creator credit, a license link, and disclosure of modifications. Version 2.0 also expects the supplied title and link to the material to be retained. `ATTRIBUTION.md` contains one attribution row per candidate.

## Metadata and provenance freeze

| Official file | SHA-256 |
|---|---|
| Validation image metadata | `ED93A0E121FE345EFFDFC7359B848DBC64A1FF6778C8C73563157CB500B33A17` |
| Validation human image labels | `D5FF236D3CDBBA36DAC1EE6F7FDF9A26934205CBEC5B933B0872722E2B6D3417` |
| V7 class descriptions | `84A4373A0EFB7FD6D93FE19B0E7CEB6C1B855C233D13B9B78A9A33655C9FDCE3` |
| Existing 76-frame seed manifest | `B6B6B95EE6F1C500F6038776CB46DC4D6B53694DD3197FFA9E5282BEC3BA851C` |
| Selected source/license manifest | `86B0FF80552253F78363CEB11297405C221480E90AF048359202E5D662300262` |
| Neutral review queue | `7514F725DBCB22DC7057E03B452B26220DB7C15B3C5140FB3A56090DAF312C3F` |
| Internal repeat map | `BFB99E891748C02136CE6234C854611A1691A89D688C22044FEC587749D6FA7D` |

The preparation runner hash is preserved separately from the final review-UI runner hash because visual QA added a display-only rotation correction after package creation. The UI reads Open Images `Rotation` and rotates only the in-memory display. Source images and concealed repeat bytes remain unchanged.

## Candidate discovery and diversity

Metadata selection used no perception model. The eligible metadata pool contained:

- 5,818 person-negative discovery rows with no positive human-category label;
- 1,109 `Person` + `Human face` discovery rows.

Open Images label absence was never interpreted as zero-hand truth. The selector balanced rare positive label signatures, coarse scene buckets, discovery category, and author identity, normally selecting at most one image per author.

| Coarse metadata scene bucket | Candidates |
|---|---:|
| Animal | 23 |
| Architecture | 22 |
| Clothing | 23 |
| Food | 23 |
| Indoor | 23 |
| Mixed | 24 |
| Nature | 22 |
| Object | 22 |
| Transport | 24 |
| Urban | 14 |

Manual spot QA confirmed varied indoor/outdoor settings, objects, buildings, food, animals, transport, portraits, group scenes, camera distances, lighting, and viewpoints. It also confirmed that some people-present candidates visibly contain hands, as expected; human review must reject those.

## Duplicate and image validation

- Download attempts: 220.
- Successful decodes and retained canonical candidates: 220.
- Download/license/dimension failures: 0.
- Exact duplicates removed: 0.
- dHash `<=4` near duplicates removed: 0.
- Pairwise exact/dHash validation against the existing 76 and all earlier retained external candidates: passed.
- All source-to-review copies: SHA-256 identical.
- All 20 repeat pairs: byte-identical.
- Four non-zero Open Images rotation records: verified and corrected at display time only.

The absence of removals means the diversity-first metadata ordering produced 220 images that already passed the frozen rules. It is not a claim that dHash measures all semantic similarity.

## Blinded review package

Reviewer question:

> Is ANY part of a human hand visible anywhere in this image?

Actions:

- `ZERO_HAND`
- `HAND_VISIBLE`
- `UNCERTAIN`

The UI presents one neutral image at a time, supports Fit/Zoom +/- and Ctrl+mouse-wheel, saves each choice atomically, resumes from the first unfinished row, and hides source labels, discovery category, attribution, prior model output, and repeat identity.

Current status is 0/240. `passed: false` is expected until every row has been reviewed.

Launch command:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_negative_gold_open_images_v7.ps1" -Command Review
```

After all rows are saved:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_negative_gold_open_images_v7.ps1" -Command Check
```

Do not finalize from raw counts. The next phase must first enforce zero `ZERO_HAND` <-> `HAND_VISIBLE` repeat disagreement, report three-class agreement, retain only canonical human `ZERO_HAND`, re-run frozen deduplication, select exactly the best 124, freeze surplus valid zeros as reserve, and then close `NEGATIVE_GOLD_V1` at exactly 200.

No MediaPipe, RTMDet, YOLO, MobRecon, RTMPose, other perception model, classifier, training, fine-tuning, Android, S4, S5, S6, or S7 work occurred.

