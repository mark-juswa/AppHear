# Negative Diversity Top-up Audit

**Date:** 2026-08-21  
**Decision:** `EXISTING_DIVERSE_POOL_SUFFICIENT_FOR_NEXT_REVIEW`  
**Scope:** existing-RGB inventory, model-independent diversity selection, and blinded-review preparation only

## Executive conclusion

Existing project RGB can plausibly fill the remaining 124-frame `NEGATIVE_GOLD_V1` deficit. After source governance and frozen image-similarity screening, 569 label-blind candidates remain. A diversity-maximized queue freezes 320 unique candidates plus 32 concealed repeats. It spans 318 clips, 49 participants, six recorded device values, and seven recorded environment values.

The semantic yield is unknown. None of the 320 candidates has been called `ZERO_HAND`; that decision belongs to the next human review. New recording is therefore **not currently justified**.

```text
CURRENT_NEGATIVE_GOLD = 76
REMAINING_TARGET = 124
DIVERSE_EXISTING_BLINDED_REVIEW_CANDIDATES = 569
NEXT_REVIEW_UNIQUE_CANDIDATES = 320
MAXIMUM_POSSIBLE_ZERO_HAND_YIELD = 320
EXPECTED_ZERO_HAND_YIELD = UNKNOWN
```

## 1. Frozen 76-frame seed

The immutable seed contains 33 corrected-gold zeros plus 43 N0 re-adjudicated zeros.

| Validation | Result |
|---|---|
| Rows | 76 |
| Exact duplicates | 0 |
| Pairwise dHash distance `<=4` | 0 |
| Positive P0 overlap | 0 |
| Protected-test rows | 0 |
| Missing source images | 0 |
| Seed manifest SHA-256 | `B6B6B95EE6F1C500F6038776CB46DC4D6B53694DD3197FFA9E5282BEC3BA851C` |

The seed status is intentionally `NEGATIVE_GOLD_V1_SEED_NOT_COMPLETE`.

## 2. Frozen dHash threshold sanity audit

The requested representative pairs were exported with side-by-side panels. The audit is a sanity check only; it did not tune the frozen rule.

| Bucket | Pair | Clip relationship | Participant/environment | Distance | Visual conclusion |
|---|---|---|---|---:|---|
| 0 | `n0_0015` / `n0_0016` | same clip | P01 / indoor | 0 | Effectively identical; exclusion is correct. |
| 1-2 | `n0_0008` / `n0_0012` | same clip | P01 / indoor | 2 | Near-identical pose and scene; exclusion is correct. |
| 3-4 | `n0_0025` / `n0_0030` | same clip | P01 / indoor | 4 | Still visibly redundant at the frozen boundary. |
| 5-6 | `n0_0040` / `n0_0066` | different clips | P01 / indoor | 6 | Similar scene but materially changed body/pose; retaining is reasonable. |

**Boundary result:** `PASS`. The `<=4` rule behaves consistently in the inspected examples, and no dHash implementation defect was found. Index and panels are under `negative_gold_v1_topup_01/dhash_threshold_sanity_index.csv` and `dhash_boundary_pairs/`.

## 3. Existing-source inventory

Old semantic labels were audited as historical metadata only. They were not used to infer truth or select the new queue.

| Source | Raw accessible material | Diversity | Old semantics / human status | Restrictions and status | Post-screen candidates |
|---|---:|---|---|---|---:|
| Corrected all-hand gold zeros | 33 frames | 33 clips, 27 signers; device/environment unknown | Direct corrected frame truth | `READY_TRUSTED_ZERO`; frozen in seed | 33 seed rows, not top-up candidates |
| Finalized N0 review | 250 canonical reviewed; 380 unreviewed residual RGB from 57 source clips | six participants, five devices, five environments | New five-class direct review for the 250 only | 43 `READY_TRUSTED_ZERO`; unreviewed residual is `BLINDED_REVIEW_CANDIDATE` | 4 residual candidates |
| C0B detector-development RGB | 424 frames, 421 clips | 36 signers; device/environment not recorded | Old box/zero-box reviews are semantically unreliable for strict absence | `BLINDED_REVIEW_CANDIDATE`; train/development lineage must be recorded | 329 |
| P1 captures | 140 frames, 30 clips | two participants, two devices, one indoor environment | Old exact review, but zero exclusions visibly contradict strict semantics | `BLINDED_REVIEW_CANDIDATE` | 21 |
| Hello-like P1 alias | RGB aliases canonical P1 | no new diversity | Same disputed semantics | `UNUSABLE_FOR_NEGATIVE_BENCHMARK` as independent evidence | 0 additional |
| A1 no-sign benchmark | four performance runs; no retained frame RGB | one signer/device | Capture instruction and logs only | `UNUSABLE_FOR_NEGATIVE_BENCHMARK` | 0 |
| A1 sentinel / A2 / RU-D phone evidence | 551 accessible selected frames from 21 attempts | one signer, Xiaomi M2101K7AG, two experiment cohorts | Prior rest/span/identity labels do not prove zero visibility | `BLINDED_REVIEW_CANDIDATE`; overlapping aliases counted once | 12 |
| RU-D retained evidence outside A2 | 2,798 images, substantially overlapping phone attempts | one signer/device | Failure-cause/span evidence, not strict zero truth | `UNUSABLE_FOR_NEGATIVE_BENCHMARK` as a separate independent source | 0 additional |
| E6 fresh negative recordings | 560 videos | one signer; capture categories include visible idle/OOV/motion | Human sequence evidence shows visible hands by design | `PROTECTED/RESTRICTED` evaluation lineage | 0 |
| ASL Citizen train/validation RGB | 50,458 source videos; 260 boundary frames decoded for the bounded audit | 40 signers; device/environment unavailable | Signing labels are not zero-hand labels; boundary frames require new review | `BLINDED_REVIEW_CANDIDATE`; train/val lineage retained | 203 |
| ASL Citizen test | 32,941 videos, 11 signers | protected test split | No usable strict zero truth | `PROTECTED/RESTRICTED` | 0 |
| Recorder/product-core material | 1,956 mixed positive/signing manifest rows | mixed signers/sessions | Positive quality review, no exact strict zero truth | `UNUSABLE_FOR_NEGATIVE_BENCHMARK` without a separately approved extraction protocol | 0 |
| HaGRID/MobileNet/ROI detector artifacts | subsets/aliases of N0, C0B, P1, or ASL Citizen | no independent source diversity | Model outputs and historical zero-box labels | `UNUSABLE_FOR_NEGATIVE_BENCHMARK` as additional evidence | 0 additional |

### C0B-specific check

The approximately 72 previously identified C0B unique-video zero-box candidates were checked explicitly:

- accessible: 72/72;
- unique clips: 72;
- signers: 30;
- device/environment metadata: unavailable;
- near current seed: six;
- near another C0B item: five;
- diversity-screened historical subset: 61.

Those 61 are review candidates, not trusted zeros. For the label-blind top-up selection, all 421 C0B clips were eligible without consulting historical zero-box labels; 329 survived global screening and 141 entered the frozen queue.

## 4. Candidate pool and queue composition

Similarity screening rejected 81 items near the 76-frame seed and 139 near an already retained candidate. It may remove redundancy but never establishes hand absence.

| Source group | Screened candidates | Frozen queue | Queue clips | Participants | Devices | Environments |
|---|---:|---:|---:|---:|---:|---:|
| C0B unique-video frames | 329 | 141 | 141 | 36 | 1 recorded value (`unknown`) | 1 recorded value (`unknown`) |
| ASL Citizen train/val boundary frames | 203 | 142 | 142 | 39 | 1 recorded value (`unknown`) | 1 recorded value (`unknown`) |
| P1 capture | 21 | 21 | 21 | 2 | 2 | 1 |
| A1/A2 phone sequences | 12 | 12 | 12 | 1 | 1 | 2 |
| N0 unreviewed residual | 4 | 4 | 4 | 4 | 4 | 4 |
| **Total** | **569** | **320** | **318 distinct clip IDs** | **49 distinct participants** | **6 recorded values** | **7 recorded values** |

Thus C0B contributes 329 usable screened candidates (141 queued), while all other sources combined contribute 240 usable screened candidates (179 queued).

The queue deliberately targets much more than the 124-frame deficit. N0's 95.2% canonical zero rate cannot be generalized across these sources, and later semantic/dedup exclusions remain possible.

Queue governance:

- randomized with frozen seed `20260823`;
- 320 unique candidates plus 32 hidden repeats using QC seed `20260824`;
- one candidate per clip initially, with further inclusion only after image screening;
- blinded to old semantic labels and every model output;
- source/config/queue hashes frozen before review;
- five permitted labels: `ZERO_HAND`, `VISIBLE_IDLE_HAND`, `VISIBLE_SIGNING_HAND`, `TRANSITION`, `UNCERTAIN`.

## 5. Diagnostic-set registry

These remain positive/hard-case diagnostics and are not negative-gold frames. Human truth is unchanged.

| Set | Instances | Frames | Selection SHA-256 |
|---|---:|---:|---|
| `RTMDET_COMPLEMENTARY_16` | 16 | 15 | `98968C14EE90DA063035F6D2B898D71520BD7794031B302DCA750D077F2E91E4` |
| `RTMDET_REGRESSION_25` | 25 | 21 | `3386A6EAA946C330ED93757ABA15F1540C88DFF36D5FFF7404482C42330A74AD` |
| `PERCEPTION_HARD_CORE_46` | 46 | 41 | `195C2C282887363CC4B04B03BE3C925F6AC6D627937A44792D37E4C0C90B9978` |

Canonical paired source SHA-256: `A416B35D985AB2B9237EE6056E080CD71089978D6CB0812A3F5A5B0FF75D4290`.

## 6. Decision and next action

**Decision:** `EXISTING_DIVERSE_POOL_SUFFICIENT_FOR_NEXT_REVIEW`.

The repository contains enough independent candidates to plausibly finish the 124-frame deficit. Existing data must be reviewed before requesting any new recording. If the eventual clean-zero yield is insufficient, the exact residual—not an assumption—will determine whether another existing-source pass or a recording specification is needed.

Run the human review:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_negative_gold_topup.ps1" -Command Review
```

After all 352 rows are saved, validate them with:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "F:\ASL DATASET\5. Apphear3\model\config\recognition_upgrade\run_negative_gold_topup.ps1" -Command Check
```

Stop after `Check`; do not infer labels or run a detector. `NEGATIVE_GOLD_V1` becomes complete only after 200 independent trusted zeros pass the frozen rules.

## 7. Reproducibility package

Package: `artifacts/recognition_upgrade/perception_backend_replacement/negative_gold_v1_topup_01`

| Item | SHA-256 |
|---|---|
| Top-up config | `C3F0A00BF5BD097A02294DA64E119E8B73C38F34F061356680331352356A520D` |
| Runner | `341812C23687DB04C4E62703AE8DDD9DAD5034F237E779B274060DF3DE390360` |
| Review queue | `D18085B853B6EAD782C34A7C036C8C2AEDE2A74B54175FEAE034397D914DBFA4` |
| Candidate manifest | `EF530BB1FF726EE2FC6202C8592C89F73F0809AEB614F461EACE7B38E9846194` |

No MediaPipe, RTMDet, MobRecon, RTMPose, other detector, landmark model, training, retraining, Android, S4, S5, S6, or S7 work occurred.
