# N0 Blinded Re-adjudication Protocol

**Status:** preregistered before candidate selection  
**Date:** 2026-08-21  
**Target:** repair the detector-negative benchmark to exactly 200 trustworthy `ZERO_HAND` frames  
**Scope:** human semantic review of existing N0 RGB only; no detector execution, training, or Android work

## 1. Frozen objective

The corrected all-hand gold package contributes 33 already governed zero-hand frames. This review
must supply 167 additional accepted, deduplicated `ZERO_HAND` frames from the existing
`n0_capture_06` RGB package. No new recording is required.

```text
TRUSTWORTHY_ZERO_HAND_EXISTING = 33
NEW_ZERO_HAND_REQUIRED = 167
FROZEN_BENCHMARK_TARGET = 200
```

The review package contains 250 unique candidate frames plus 25 hidden repeat-QC rows. Repeat rows
measure reviewer consistency and never count as additional benchmark candidates.

## 2. Blinding and prohibited information

Candidate selection may use only source image hashes and capture metadata: participant, device,
environment, clip, timestamp, and frame index. It must not read or use:

- the old N0 human label;
- MediaPipe, RTMDet, or any other model output;
- P0 false-positive status or failure-panel membership;
- recognition output;
- filenames as semantic truth.

The reviewer sees the center RGB frame and a chronological five-frame context strip. The reviewer
does not see old labels, detector overlays/scores, eligibility, participant/device/environment,
or whether a row is a hidden QC repeat.

## 3. Frozen semantic classes

| Class | Exact rule | Eligible as detector negative? |
|---|---|---|
| `ZERO_HAND` | No human hand pixel is visibly present anywhere, including fingertips, lap hands, crossed-arm hands, blurred hands, and edge-clipped hands. | Yes |
| `VISIBLE_IDLE_HAND` | One or more hands are visible while the person is not actively signing. | No |
| `VISIBLE_SIGNING_HAND` | One or more hands are visible during active signing-like movement. | No |
| `TRANSITION` | A hand is entering/leaving, or the context shows an entry/exit boundary that prevents a stable state label. | No |
| `UNCERTAIN` | Resolution, blur, clipping, or ambiguity prevents a confident decision. | No |

Conservative rule: if the reviewer is not certain that absolutely no hand pixel is visible, do not
choose `ZERO_HAND`.

## 4. Frozen candidate-selection policy

Source: all 630 center images and metadata in
`artifacts/recognition_upgrade/e2e_c0/n0_capture_06`.

1. Verify all source images and source videos exist and validate their recorded hashes.
2. Exact-deduplicate center images by SHA-256. For an exact duplicate group, retain the
   lexicographically first source sample ID as the canonical candidate.
3. Use deterministic seed `20260821`.
4. Select 250 unique candidates with seeded round-robin balancing across participant, device,
   environment, and clip. No clip may contribute more than five candidate frames.
5. Within a clip, require selected timestamps to be at least 1,000 ms apart.
6. Randomize review order independently of source/sample order.
7. Select 25 hidden repeat-QC rows using seed `20260822`; distribute repeats through the review
   order and assign neutral review IDs that do not reveal duplication.

If these constraints cannot produce 250 unique candidates, preparation must stop with an error;
the constraints must not be silently weakened.

## 5. Review and quality-control policy

- Primary reviewer: the developer operating the local GUI.
- Every row is explicitly accepted after one of the five classes is chosen.
- Work is resumable and saved atomically after each accepted row.
- The 25 hidden repeats are scored only after all review rows are complete.
- Repeat agreement must be at least 92% (at least 23/25 exact matches).
- A `ZERO_HAND` versus any non-zero disagreement is a critical disagreement.
- If repeat agreement fails, or any critical disagreement exists, no benchmark is frozen. The
  conflicting originals and repeats require a separately recorded adjudication pass; neither label
  wins automatically.
- `UNCERTAIN` and `TRANSITION` rows are excluded, not forced into another class.

This QC establishes intra-reviewer repeatability. It is not a claim of independent two-reviewer
agreement. A future second reviewer may recheck the final 167-frame slice, but that is not required
to complete this bounded repair unless repeat QC fails.

## 6. Frozen final-selection and diversity policy

After a passing review/QC gate:

1. Collapse hidden repeats to their canonical source row; repeats never increase the count.
2. Keep only exact `ZERO_HAND` rows.
3. Exact-deduplicate again and reject any dHash near-duplicate pair with Hamming distance <=4,
   keeping the earlier deterministic diversity-ranked row.
4. Select 167 new zeros using metadata-only round-robin balancing.
5. First pass: at most three accepted frames per clip.
6. Only if fewer than 167 are obtained, permit a fourth frame per clip to fill the documented
   shortfall. Never permit a fifth frame in the frozen benchmark.
7. Required representation: all six participants, all five devices, all five environments, and at
   least 50 of the 57 clips.
8. The 33 corrected-gold zeros remain unchanged and are appended to form the 200-frame benchmark.

If fewer than 167 accepted N0 zeros survive QC, deduplication, and diversity constraints, report the
exact deficit. Do not silently add disputed C0B/A2/P1 labels or record new data.

## 7. Required provenance and outputs

Preparation records branch, HEAD, worktree status, source file hashes, source image hashes, source
video hash verification, evaluator/runner/config hashes, Python/OpenCV versions, seeds, and the
exact selection rules.

Required package files:

- `candidate_manifest.csv` — internal source mapping and capture metadata;
- `review_queue.csv` — neutral IDs, image paths, review state, and semantic label only;
- `source_hash_manifest.json`;
- `provenance.json`;
- copied/link-free `center_images/` and `context_panels/` assets;
- after review: `review_check.json`, `qc_result.json`, `new_zero_hand_167.csv`, and
  `frozen_zero_hand_200.csv`.

The package must refuse to overwrite existing review state.

## 8. Stop conditions

Stop without freezing a benchmark if:

- source provenance or image/video hashes fail;
- selection constraints cannot be met;
- review rows are incomplete;
- repeat agreement is below 92%;
- any critical repeat disagreement remains unresolved;
- fewer than 167 new zeros survive final gates;
- required participant/device/environment/clip diversity is not met.

No detector, model, training job, Android code, S4-S7 component, or production asset may be run or
changed as part of this protocol.

