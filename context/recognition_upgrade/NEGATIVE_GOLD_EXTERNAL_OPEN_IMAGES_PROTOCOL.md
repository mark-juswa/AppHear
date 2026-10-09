# NEGATIVE_GOLD_V1 External Open Images Protocol

**Protocol:** `apphear.negative_gold.external.open_images.v7.v1`  
**Purpose:** obtain diverse RGB candidates for human zero-hand adjudication  
**Scope:** benchmark governance only; no perception-model execution or training

## Frozen objective

`NEGATIVE_GOLD_V1` has 76 trusted, diversity-clean `ZERO_HAND` images. The target is 200, so the exact deficit is 124. This package will contain 220 canonical Open Images candidates plus 20 concealed exact repeats. It does not supply ground truth. Only later human review can label an image `ZERO_HAND`.

## Source and licensing

- Dataset: Open Images V7, validation split, released October 2022.
- Image metadata: official `validation-images-with-rotation.csv` containing Open Images ID, original URL, original landing page, author/profile, title, per-image license, original size/MD5, thumbnail, and rotation.
- Discovery annotations: official human image-label CSV, used only for coarse candidate discovery and diversity.
- Annotation license: CC BY 4.0.
- Eligible image license: exact per-image CC BY 2.0 metadata, with non-empty author, original URL, and original landing page.
- Pixel access: bounded individual downloads from the official CVDF `open-images-dataset` validation mirror.

Open Images expressly disclaims warranties about individual image-license status. The package therefore preserves the complete per-image attribution record. Any redistribution or public product use must re-check the original landing page and comply with attribution, privacy, publicity, and other applicable rights.

Attribution must preserve creator/author, supplied title, source or landing-page link, CC BY 2.0 license link, and an indication of modifications when applicable. Annotation reuse must credit Open Images/Google and link CC BY 4.0.

## Candidate discovery

Metadata may be used only to build a varied review pool:

- 143 `PERSON_FREE_DISCOVERY` candidates: human-verified negative `Person` image label and no positive human-category label;
- 77 `PEOPLE_PRESENT_DISCOVERY` candidates: positive `Person` and `Human face` image labels;
- positive object/scene labels may balance coarse scenes and rare label signatures;
- normally one selected image per author;
- deterministic selection seeds freeze ordering and hidden repeats.

These discovery categories are hidden from the reviewer and are not semantic truth. Missing hand annotations, negative person labels, and absent labels never prove `ZERO_HAND`.

Selection must not use MediaPipe, RTMDet, YOLO, a hand detector, a classifier, embeddings produced for this task, model confidence, or any prior hand prediction.

## Frozen duplicate rules

- Exact image SHA-256 duplicates are rejected.
- The existing project 64-bit dHash is computed from a 9x8 grayscale resize.
- A candidate is rejected when its dHash Hamming distance is `<=4` from the frozen 76-image seed or an already retained external candidate.
- The threshold is frozen before review and cannot be tuned afterward.

## Human review

The only reviewer question is:

> Is ANY part of a human hand visible anywhere in this image?

Allowed labels:

- `ZERO_HAND`: absolutely no fingertip, palm, partial, clipped, blurred, lap, face/chest-adjacent, or tiny distant hand is visible;
- `HAND_VISIBLE`: any visible hand evidence;
- `UNCERTAIN`: the reviewer genuinely cannot decide.

The UI hides Open Images labels, discovery category, source filename semantics, model output, and repeat identity. It randomizes presentation and contains 20 concealed byte-identical repeats.

## Hard QC and later finalization

- all 240 review rows must be accepted;
- there must be zero `ZERO_HAND` <-> `HAND_VISIBLE` hidden-repeat disagreements;
- overall three-class agreement is reported;
- hidden repeats never count toward the benchmark;
- `UNCERTAIN` and `HAND_VISIBLE` never enter negative truth.

In the separately approved finalization phase, keep only canonical `ZERO_HAND` rows, re-run exact/dHash checks against the frozen 76, diversity-rank them, select exactly 124 if available, freeze additional valid zeros as `NEGATIVE_GOLD_RESERVE`, and then freeze `NEGATIVE_GOLD_V1` at exactly 200. Stop afterward.

