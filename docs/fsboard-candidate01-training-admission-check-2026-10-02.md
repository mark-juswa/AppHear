# FSboard Candidate01 training-admission check

2026-10-02 (Asia/Manila). User approved the bounded next check after the exact twelve selected
TRAIN originals were downloaded and verified. **This diagnostic check is complete; training
admission is on hold.** Source/raw conversion is verified for three clips, nine are quarantined
before extraction, and none is admitted to model training. This does not reverse the governing
`FSBOARD_COMPATIBLE_WITH_LIMITS` corpus/architecture decision.

## 1. Repository and governing records — VERIFIED

- Branch `codex/current-working-text-to-asl-baseline-2026-09-29`, HEAD
  `cc1f3949114d0ed1dab38d4428191151b37df358`, unchanged.
- Protected WORD baseline `76d93cecd85bf9f76064d320aa4a5791b5f0704a`; the existing 883-file
  protected source/asset snapshot matches, zero mismatches. No reset, merge, branch switch,
  staging, commit, production/Android/Context Assist modification or new model training.
- Starting modified readiness report, feature-schema, progress tracker and memory, and all
  untracked AZ/FSboard/phone-pull/scratch work are preserved. Handoffs are append-only.
- AZ-0, AZ-1, the FSboard compatibility gate, download-preparation report and source-integrity
  report remain governing. The real AZ-1 package is unchanged, with zero humans/sessions/samples.
- Fixed inventory: official `googleai/fsboard` v13 TRAIN; twelve original MP4s, twelve official
  signer IDs, six DAUN/six MacKenzie, 97,918,150 bytes. Manifest SHA-256:
  `23f1bf347f016f3ffe208d4dc181038c1d814a00c4c340c0dc669b0db9bcd000`.
  No additional downloads or DEV/TEST payload inspection. The original selection is unchanged.

## 2. Decode, cadence and orientation — VERIFIED all twelve

Independent FFprobe 8.1 and the **existing** `iter_video_frames(video,None)` decoded all
**2,292 frames**, matching declared/read counts for every source. All indices are consecutive,
all PTS are finite and increasing, and OpenCV timestamps match FFprobe within **0.000445 ms**.
Every frame uses `CONTAINER_POS_MSEC`; no fallback/repair, resampling, trimming or synthetic frames.
This proves complete decoding of the released clips, not complete linguistic attempts or absence
of camera-side dropped frames.

| # | Stratum / signer | Transcript | Frames | Stored dimensions | Average FPS | Container duration s | Reflection / extraction |
|---|---|---|---:|---|---:|---:|---|
| 1 | DAUN / 1d72 | jade hughes | 121 | 2688×1512 | 30.08 | 4.023 | UNKNOWN / quarantined |
| 2 | DAUN / d69c | surprise az | 181 | 3264×1836 | 29.91 | 6.052 | UNKNOWN / quarantined |
| 3 | DAUN / 917d | sommer stevens | 121 | 3264×1836 | 30.03 | 4.030 | UNKNOWN / quarantined |
| 4 | DAUN / 740f | rochelle velez | 181 | 3264×1836 | 29.91 | 6.052 | UNKNOWN / quarantined |
| 5 | DAUN / d3ab | octavio hamilton | 91 | 3264×1836 | 29.92 | 3.042 | UNKNOWN / quarantined |
| 6 | DAUN / c7d4 | kimberlee hammond | 241 | 3264×1836 | 30.05 | 8.021 | UNMIRRORED / extracted |
| 7 | MacKenzie / 6f68 | love means many things | 121 | 3264×1836 | 23.94 | 5.054 | UNKNOWN / quarantined |
| 8 | MacKenzie / 03ad | communicate through email | 241 | 3264×1836 | 30.01 | 8.031 | UNMIRRORED / extracted |
| 9 | MacKenzie / 4f1e | just like it says on the can | 151 | 3264×1836 | 30.03 | 5.029 | UNMIRRORED / extracted |
| 10 | MacKenzie / 9d2b | an excellent way to communicate | 301 | 3264×1836 | 29.89 | 10.070 | UNKNOWN / quarantined |
| 11 | MacKenzie / fe96 | labor unions know how to organize | 211 | 3264×1836 | 29.89 | 7.059 | UNKNOWN / quarantined |
| 12 | MacKenzie / 1f91 | shivering is one way to keep warm | 331 | 3264×1836 | 30.03 | 11.023 | UNKNOWN / quarantined |

All have a 270° clockwise OpenCV orientation value, consistent with FFprobe's 90° display-matrix
rotation and the pinned collection-source comment on the sign convention. Automatic rotation was
disabled; the frozen explicit rotation produces upright 1512×2688 or 1836×3264 RGB. Stored video
dimensions/codec rotation are now verified; preview orientation was not used as evidence.
Native median/p95 frame gaps are approximately 33.24–33.46 / 33.30–33.51 ms except clip 7,
41.76 / 41.87 ms. These are video observations, not phone-delivered Candidate01 cadence.

Container durations differ from `clipEndTimeS-clipStartTimeS` by roughly one final frame interval;
both measurements are retained. Publisher annotation start/end lie inside metadata clip bounds
for all twelve. No letter timing or clip-completeness approval is inferred from this containment.

## 3. Saved-pixel reflection — VERIFIED scope, nine unresolved

Direct normal left-to-right physical text establishes unmirrored saved pixels for:

- **6:** “Durable / Presentation” text on a binder in the original saved frame.
- **8:** “PANTHER COFFEE” clothing text.
- **9:** readable clothing text including “lovebugs” and “poison”.

Native-frame reference crops, frame indices, source hashes and crop coordinates are retained in
`admission_check_01/review/` and linked by `evidence/reflection_review.json`. Evidence applies only
to each exact source clip; it does not certify another clip/signer/session or the entire release.
No flip, OCR, recognition score or inferred dominant hand established these facts.

For **1–5, 7, 10–12**, no decisive saved-pixel asymmetric reference was established. UNKNOWN
does not mean mirrored. Positive display-matrix rotation and the public Camera2/MediaRecorder source
support a convention but do not identify the installed historical build/session. These nine remain
in inventory, with original transcripts, **no extraction and no training admission**. No replacement
clips, forced pixel transforms, default approvals or OTHER relabels.

Review crops/contact sheets are private local diagnostic material, ignored by Git and not embedded
in this report. A coarse torso crop may still contain faces; it is not a privacy-redacted publication
asset. No face reidentification or public unblurred image publication occurred.

## 4. Frozen Candidate01 → raw-v1 — VERIFIED three sources

The wrapper delegates once per frame to the original `Candidate01Offline.process_rgb` and uses
unchanged `extract_video`, `save_raw_sequence`, `load_raw_sequence` and schema validation.
It adds timing-only instrumentation and diagnostic metadata, not perception/feature math.
Original upright RGB is the input; review crops never enter inference. Default CPU execution and
native variable time are retained, with no delegate/thread/threshold tuning or carry-forward.

Pinned model SHA-256:

- DWPose-t ONNX: `37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0`.
- Hand-refiner TFLite: `6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9`.

The four original preprocessing/raw source-module hashes also match the prior gate.
All **633 raw frames** pass schema, shapes, masks, finite valid XY, indices, PTS and frozen
observed-hand/presence/ROI/body-availability invariants. PTS still agree with FFprobe within 0.001 ms.

| # | Whole-clip hand observed | Missing any hand | Metadata-window hand observed* | L/R observed frames | Body available | Candidate p50/p95 ms |
|---|---|---|---|---|---:|---|
| 6 | 194/241 (80.5%) | 47 | 193/221 (87.3%) | 191 / 151 | 1/241 | 52.88 / 55.65 |
| 8 | 174/241 (72.2%) | 67 | 169/190 (88.9%) | 174 / 62 | 98/241 | 51.63 / 55.73 |
| 9 | 134/151 (88.7%) | 17 | 130/131 (99.2%) | 75 / 134 | 0/151 | 53.88 / 56.45 |

*Publisher clip-level annotation bounds mapped by subtraction into the clip timeline; their
linguistic alignment is not independently verified. They are **not letter boundaries**. These
fractions are hand-mask diagnostics, not letter accuracy or corpus usability estimates. Whole-clip
counts include lead-in/release. Runtime timing is desktop CPU `process_rgb`, not phone cadence or
end-to-end model latency; extraction wall times are 17.84 / 17.52 / 11.58 seconds.

Missing-hand runs and symptoms needing review:

- Clip 6: final 29-frame missing run from 7.056–7.988 s; internal 4-frame gap at 4.693–4.793 s.
- Clip 8: final 42-frame missing run from 6.632–7.998 s; internal 5-frame gap at 4.799–4.932 s.
- Clip 9: initial 10-frame missing run, one missing frame at 4.129 s and short end gaps.

Sampled final saved frames of 6/8 show lowered/absent signing hands, consistent with release;
this does not explain every earlier missing frame or certify transcript completion. ROI/proposal
and refiner failures cannot be separated from capture/visibility/boundary issues from masks alone.
No definite failure cause is assigned without paired temporal review.

Closely overlapping L/R ROIs occur in **146/148**, **27/62**, **75/75** simultaneously observed
slot frames, using the earlier gate's diagnostic center-distance rule (<0.25×smaller ROI side).
This is not hand-identity truth: two slot observations may refer to the same physical hand.
Independent anatomical/dominant-hand correctness and left-handed coverage remain unverified.
Partial body points remain in raw even when complete body availability is false; no feature blocks
are dropped and no final feature vector is derived.

## 5. Lineage / integrity / review state — VERIFIED and explicitly pending

Three `apphear.fsboard.admission_check_receipt.v1` diagnostic receipts pin stable manifest sample IDs,
official TRAIN/signers/transcripts, source size/MD5/SHA-256, model/source/wrapper hashes, raw SHA-256,
source semantics review, decode probe, frame indices/counts, actual PTS and raw schema.
Each output is `NOT_ADMITTED_REVIEW_PENDING`; it is not an AZ-1 admission receipt or CTC training package.
The legacy raw metadata `class_id=-1` is an unused compatibility sentinel, not a letter/model target.

Raw retains common phone evidence: 2D hand XY, joint/observed/proposal masks, support/presence/ROI,
eight body XY/support/masks/availability, source size, indices and real timestamps.
Python-only diagnostic handedness is preserved for audit and excluded from future common input;
Z/world/profiling/signer/transcript fields are not model inputs. No feature adapter/parity claim,
378/258/208 features, Recognition V2, word ingest, AlphabetSession or runtime routing.

Actual-artifact validation passes source inventory, JSON/CSV identities, all twelve roles/signers,
quarantine non-extraction, the three source/raw/receipt hash chains, masks/dtypes/chronology/PTS,
and exact protected-model/source identity. **45 existing AZ/raw/download tests pass.** No policy
or admission threshold was weakened. The AZ-1 interval validator is not misapplied to phrase-CTC data.

All twelve entries in `linguistic_review_queue.json` remain pending with no fabricated reviewer,
transcript approval, J/Z completion, temporal boundaries or repeat-occurrence approval. Adjacent
repeated-character indices come only from text and are explicitly not video labels. Clip 6 retains
EE and MM, clip 8 MM, clip 9 J. **Full J trajectory and both occurrences of repeats are not yet
verified. Z and LL perception are untested**, because their selected sources are quarantined.

## 6. Decision and next bounded action

**GO:** the original source → frozen Candidate01 → chronological raw-v1 → diagnostic receipt path
works on three source-verified clips. Decode works on all twelve.

**HOLD:** broader dataset admission/training is not justified. Resolve saved-pixel reflection for
the nine fixed sources via decisive original-pixel evidence or reliable release/session/build
attestation; retain their identities. Obtain qualified full-transcript/J/Z/repeat temporal review,
including the missing-hand runs and ROI slot ambiguity. Only then extract the remaining eligible
sources once and complete the representative assessment. Do not replace uncertain clips with easy
ones or change Candidate01 to make this sample pass.

The future sequence dataset/validator, common-input parity, resolution/framing and measured phone
cadence, evaluation-policy/historical identity governance and rejection requirements remain separate
gates. This diagnostic does not authorize training, another corpus/model search or Android work.
There is no need to download more files to continue this fixed sample review.

Evidence is under
`datasets/fingerspelling/fsboard_candidate01_admission_20261002/admission_check_01/`.
Read `evidence/validation_result.json`, `video_probe.json`, `reflection_review.json`,
`candidate01_results.json`, the three receipts and `linguistic_review_queue.json`.
Exact helper snapshots and an evidence hash index are preserved; previous gate evidence is untouched.

FSBOARD_TRAINING_ADMISSION_HOLD
