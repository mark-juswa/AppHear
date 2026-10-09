# FSBOARD_COMPATIBILITY_GATE

2026-10-02. **Decision: FSBOARD_COMPATIBLE_WITH_LIMITS.** FSboard v13 can supply a substantial,
signer-disjoint RGB/transcript corpus and can be re-extracted by frozen Candidate01. Recommend it as
the primary **sequence-data source**, with a small causal temporal convolutional encoder, character
CTC training and a host CTC decoder. This establishes source/dialect feasibility, **not** sufficient
perception quality, fluent phone performance, admitted training data or permission to begin training.

VERIFIED denotes downloaded official metadata, source inspection or the four actual TRAIN extractions.
PROPOSED denotes future contracts/architecture. UNKNOWN denotes an unresolved evidence gap.
AZ-0/AZ-1 remain the governing completed audit/foundation; this gate changes the recommended next
direction, not their implemented isolated A–Z + OTHER contract or coverage policy.

## 1. Repository and official payload/access — VERIFIED

Branch `codex/current-working-text-to-asl-baseline-2026-09-29`; HEAD
`cc1f3949114d0ed1dab38d4428191151b37df358`. Protected word baseline remains
`76d93cecd85bf9f76064d320aa4a5791b5f0704a` through the S2-R2 baseline branch, stable RU-D10
branch and peeled `apphear-s2-r2-integration-complete-2026-09-26` tag. No Git state transition occurred.
Pre-existing modified readiness report, feature-schema, progress tracker and memory were preserved;
AZ documents/tooling/datasets, `.codex_tmp`, sentinel CSV and four `phone_pull*` roots were already
untracked. Only this gate's evidence/report and append-only handoffs/registry note were added.
The preceding custom smoke was superseded before capture or enrollment into the package; no custom
videos were collected and no recorder/main-app installation was performed for this gate.

[Official Kaggle release](https://www.kaggle.com/datasets/googleai/fsboard), queried anonymously through
`/api/v1/datasets/view/googleai/fsboard` and `/api/v1/datasets/list/googleai/fsboard?pageSize=1000`,
reports v13, updated 2025-07-26, **1,451,641,027,485 bytes** (~1.45 TB / 1.32 TiB), and explicitly
states that RGB clips and validation/test sets are included. The API limits this listing to 200 files
with pagination; the saved first page is not falsely presented as a complete corpus listing.

Verified layout from that inventory and successful individual-file downloads:

```text
LICENSE
convert_arrow_to_parquet.py
daun_v3/
  metadata/daun_v3-{train,validation,test}.json
  video_clips/daun_v3-{train,validation,test}/<clipFilename>.mp4
  landmarks/daun_v3-<split>.arrow-<shard>-of-<count>
dmk_v3/
  metadata/dmk_v3-train.json
  video_clips/dmk_v3-train/<clipFilename>.mp4
```

The downloaded MacKenzie metadata has TRAIN only; the attempted `dmk_v3-validation.json` URL
returned 404. Do not manufacture MacKenzie evaluation partitions. Current landmark delivery uses
Arrow/Feather shards containing serialized TensorFlow SequenceExamples: the supplied converter
actually calls `pyarrow.feather.read_table(..., columns=['serialized'])`. Its generated Parquet and
supplemental CSV are outputs, not the RGB/transcript input used here. The descriptive data card's
older TFRecordio wording does not accurately name these v13 containers. No landmark shard was fetched.

Each JSON row links `clipFilename`, `phrase`, `signerId`, `collectionId`, `fullVideoFilename`,
annotation/session and clip start/end seconds, original clip size/MD5 and creation provenance.
DAUN also carries `sensitiveContent`. Filename signer prefixes match all 150,754 rows. These are
**phrase/clip** annotations, not letter boundaries. Metadata has no trustworthy signer handedness,
per-video mirror attestation, decoded FPS/resolution, or human-per-letter review.
Original RGB here means the released camera-video **clips**. The `fullVideoFilename` provenance field
does not establish that complete uncut session videos are downloadable in this package.

Individual access is demonstrated with
`/api/v1/datasets/download/googleai/fsboard/<URL-encoded-file-path>?datasetVersionNumber=13`:
four complete JSON metadata files, LICENSE, converter, and **four TRAIN MP4s totaling 20,998,358 bytes**.
Downloaded official files total 130,159,520 bytes; no full-corpus download or TEST video/landmark payload
access occurred. Local identities/hashes are in [download-identities.json](../datasets/fingerspelling/fsboard_gate_20261002/evidence/download-identities.json).

The fetched LICENSE explicitly licenses DAUN/DMK under **CC BY 4.0**. Preserve Google attribution,
FSboard citation, license link and modifications notice. The data card asks users to blur faces in
public examples, avoid reidentification/deepfakes and respect the Deaf community. Original video and
private review imagery are locally ignored; the report publishes no signer imagery. These dataset
conditions are separate from the earlier landmark competition's rules. [License terms](https://creativecommons.org/licenses/by/4.0/).

## 2. Usable alphabet subset — VERIFIED metadata, not verified performances

Filter: entire transcript matches ASCII `[A-Za-z ]+`, contains a letter; uppercase is the sole
normalization. No punctuation/digit stripping, substring cropping, invented labels or boundaries.
Official `train/validation/test` map to TRAIN/DEV/PROTECTED_TEST without moving humans.

| Official role | All sequences | Retained sequences | Retained humans | Retained source-video bytes | Metadata clip hours |
|---|---:|---:|---:|---:|---:|
| TRAIN | 126,203 | 64,410 | 117 | 554,424,412,294 | 130.85 |
| DEV | 12,022 | 2,352 | 15 | 14,596,134,846 | 3.37 |
| TEST | 12,529 | 2,614 | 15 | 18,281,830,134 | 4.00 |

Total: **69,376 sequences, 147 humans, 1,516,137 letters and 259,716 spaces**. TRAIN comprises
55,504 MacKenzie and 8,906 DAUN sequences; DEV/TEST are DAUN. Training is therefore dominated by
common phrases, while evaluation contains shorter open-vocabulary strings: report strata separately
and avoid a lexicon/language model that conceals visual failures.

| Character | TRAIN | DEV | TEST |
|---|---:|---:|---:|
| A | 114979 | 3818 | 4158 |
| B | 21978 | 518 | 557 |
| C | 42748 | 1304 | 1511 |
| D | 48558 | 935 | 1036 |
| E | 180928 | 2905 | 3067 |
| F | 28626 | 485 | 487 |
| G | 32629 | 657 | 687 |
| H | 63355 | 860 | 937 |
| I | 104593 | 2310 | 2561 |
| J | 5054 | 227 | 237 |
| K | 17357 | 456 | 530 |
| L | 60531 | 2093 | 2272 |
| M | 36211 | 841 | 916 |
| N | 92381 | 2673 | 2870 |
| O | 118467 | 2292 | 2486 |
| P | 29130 | 429 | 440 |
| Q | 3114 | 40 | 35 |
| R | 97506 | 2354 | 2625 |
| S | 95046 | 1747 | 1906 |
| T | 124959 | 1456 | 1592 |
| U | 45784 | 625 | 642 |
| V | 18225 | 410 | 464 |
| W | 27436 | 407 | 419 |
| X | 4051 | 180 | 200 |
| Y | 36224 | 489 | 670 |
| Z | 2165 | 135 | 151 |

J occurs in 4,910/216/233 sequences and Z in 2,007/127/146. J/Z occur for all 15 humans in each
evaluation role; TRAIN has J for 116 and Z for 114 humans. This confirms transcript coverage,
not complete visible trajectories. Adjacent equal-letter pairs occur in 30,738/832/868 sequences;
LL counts are 9,290/324/360, MM 1,117/14/15, EE 7,651/71/88. MM covers 101/8/10 humans.
DEV/TEST have no adjacent ZZ pairs despite individual Z coverage. Repeats are counted within the
original string; `A A` is not counted as `AA`.

Character length including spaces, min/p25/median/p75/p95/max:
TRAIN `3/23/28/31/37/43`, DEV `4/12/13/16/21.45/31`, TEST `1/11/13/16/21/28`.
Median metadata clip durations are 7.00/5.00/5.02 seconds. Relevant TRAIN strings include
`angel mcconnell`, `martin gentry`, `gustavo ho`, `mohammed kim`; alphabetic URL fragments also
survive. DAUN metadata does not distinguish names/places/URLs row by row, so a precise names/places
count is UNKNOWN. Their synthetic generation and domain categories are documented by the
[authors](https://arxiv.org/html/2407.15806v1).

All roles are signer-disjoint, before and after filtering. No same-MD5 copies occur within/between
retained roles. TRAIN shares zero normalized phrases with DEV/TEST, but **465 distinct normalized
phrases overlap between DEV and TEST**, contrary to a blanket all-role phrase-disjoint interpretation
of the paper. Removing overlapping DEV phrases would leave 1,371 DEV sequences and all 15 DEV humans
(981 removals); this is a quantified **proposal**, not an applied filter. Freeze that decision before
model selection, retain official human roles and TEST, and document the v13/paper discrepancy.
See [statistics](../datasets/fingerspelling/fsboard_gate_20261002/evidence/subset-statistics.json) and
[additional audit](../datasets/fingerspelling/fsboard_gate_20261002/evidence/additional-metadata-audit.json).

## 3. Candidate01 extraction — VERIFIED, with quality/semantics limits

Used unchanged `pipeline/perception_vnext/offline_candidate01.py:Candidate01Offline`,
`extract_video`, `iter_video_frames(video,None)` and raw-schema `save_raw_sequence/load_raw_sequence`.
One inference per decoded frame, no resampling, flips, carry-forward, final feature builder or word
ingest. Model SHA-256:

- DWPose: `37b0f265200f8e249adba1cc9b62925f5e1252245580ed1f66f583d7bce239c0`.
- Refiner: `6acda74af3fbf40e68265c20c7394b2bad81a16a481dcd79ad7a081887c3d6b9`.

Each TRAIN source matched its official file size/MD5; additional SHA-256 identifies source → NPZ →
receipt. Receipts pin all four perception-module hashes, wrapper hash, Git revision, OpenCV/FFmpeg
decoder identity, indices, timestamps and native variable cadence. These are explicitly
`apphear.fsboard.compatibility_receipt.v1` **diagnostic receipts**, not AZ-1 admission approvals.

| TRAIN signer / phrase | Frames | Average container FPS | Last PTS ms | Any observed hand | Missing any hand | L/R observed frames | Body available |
|---|---:|---:|---:|---:|---:|---:|---:|
| d69c / joe hunt | 91 | 26.21 | 3438.93 | 62 (68.1%) | 29 (31.9%) | 41 / 60 | 0 |
| d8ef / scotty meza | 91 | 27.57 | 3259.29 | 65 (71.4%) | 26 (28.6%) | 57 / 63 | 0 |
| e96d / tammie reeves | 91 | 23.91 | 3763.66 | 7 (7.7%) | 84 (92.3%) | 3 / 4 | 0 |
| a95b / not quite so smart as you think | 181 | 30.03 | 5994.47 | 148 (81.8%) | 33 (18.2%) | 135 / 148 | 10 |

All store 3264×1836 pixels with 270° clockwise orientation metadata; existing rotation yields upright
1836×3264 RGB. All declared frames decode; indices are consecutive and timestamps strictly increasing,
entirely `CONTAINER_POS_MSEC`. Median/p95 gaps in ms: `41.63/41.83`, `33.53/41.94`, `41.82/41.90`,
`33.30/33.30`; respective maxima `50.02/50.24/41.93/33.54`. No timestamp repair occurred.
Container average FPS is not a uniformly sampled timeline or proof of no camera-side frame loss.

Raw schema/shapes/finite valid XY/chronology and frozen observed/presence/≥18-joint/ROI and body-mask
rules passed all four samples (454 frames). Whole-clip missing-hand percentages include lead-in/out;
they are not measured letter miss rates. MM-containing e96d has proposals in 69/87 L/R frames but
only 3/4 accepted observations, with median proposed-slot presence ~0.027/0.031. Low refiner acceptance
is verified; its cause and linguistic clip completeness are UNKNOWN. Do not retune or relabel it OTHER.

For the J/Z clips, simultaneous L/R observations often have ROI centers closer than 0.25 times the
smaller ROI side (37/39 and 54/55 simultaneous frames). Anatomical slot names do not prove two physical
hands or signer dominance; duplicate proposals/slot ambiguity need review. Left-handed coverage was
not independently established. No character bounds were invented, so full J/Z motion and both MM
occurrences are **not verified** merely from phrase membership and nonzero hand coverage.

Readable `THE GOONIES` clothing print establishes unmirrored saved pixels for d8ef; upright pose is
visually consistent after the metadata rotation. Reflection remains unverified for the other three.
The collection app's pinned public source at `5c933de...` uses direct Camera2 → MediaRecorder SURFACE,
an orientation hint, and a separate preview transform; its clip utility describes codec-copy cuts.
This supports the source convention but is not a proven build identity for every 2021–2023 capture.
**The extractor's hardcoded `UPRIGHT_UNMIRRORED_SOURCE_RGB` string is not reflection evidence.**
All four stay diagnostic-only; unknown reflection must be resolved before training admission.
[Collection source](https://github.com/Accessible-Technology-in-Sign/RecordTheseHands/blob/5c933debadb73be24d4f663547699802f053775c/app/src/main/java/edu/gatech/ccg/recordthesehands/recording/RecordingActivity.kt).

Results/receipt references: [DAUN](../datasets/fingerspelling/fsboard_gate_20261002/evidence/candidate01-results.json),
[DMK](../datasets/fingerspelling/fsboard_gate_20261002/evidence/candidate01-dmk-result.json),
[coverage diagnostics](../datasets/fingerspelling/fsboard_gate_20261002/evidence/coverage-diagnostics.json).

## 4. Common training/deployment input — VERIFIED fields, PROPOSED adapter

`recognition_schema.py:RawSequence` ↔ `android/.../perceptionvnext/PhoneCausalCore.kt:PhoneRawObservation`:

| Python raw field | Android field | Common shape / use |
|---|---|---|
| frame_index, timestamp_ms, source_size | sourceIndex, timestampMs, sourceWidth/Height | Provenance, real dt and normalization dimensions |
| hand_xy | handXy | `[T,2,21,2]`, Android flattened per hand |
| hand_joint_valid, hand_observed | handJointValid, handObserved | `[T,2,21]`, `[T,2]`, effective geometry validity |
| hand_proposal_support, hand_presence | handProposalSupport, handPresence | `[T,2,21]`, `[T,2]`, unchanged support/presence |
| hand_proposal_present, hand_roi_center_side | handProposalPresent, handRoiCenterSide | `[T,2]`, `[T,2,3]`, current proposals/ROI |
| body_xy/support/valid/available | bodyXy/Support/Valid/Available | Eight L/R shoulder/elbow/wrist/hip points, masks and group availability |

Both use anatomical slots from DWPose indices 91/112 and body indices 5–12. Exclude Python-only
`hand_handedness_diagnostic`, refiner Z/world outputs, metadata/transcript/signer/split, and Android-only
profiling timing from model inputs. A missing ROI has NaN geometry in Python, zero geometry in Android,
false masks on both, and **NaN Android handPresence**; AZ-1's masked-zero summary is a geometry
simplification, not a presence-value specification. Invalid finite geometry must also respect masks.

PROPOSED `FingerspellingFeatureAdapter.v1` / `apphear.fingerspelling.input.v1`: variable-time named
common hand/body evidence, effective validity, proposal/presence/support, ROI, relative timestamps/dt,
plus true-length/padding mask. Canonicalize invalid geometry to zero **with explicit masks**; retain
real missing-hand frames, preserve partial valid body points even if bodyAvailable=false, and never
forward-fill or infer visibility. Retain both hands. Derive source-normalized wrist/fingertip paths
and mask-gated wrist-relative geometry with a valid current hand scale; avoid requiring complete-body
normalization, which fails in these close selfie views. Normalization arithmetic, ordering, additional
derived channels and packing width need a new explicit parity-tested contract. No final D or window
length is frozen here; 378, 208 and `[96,350]` are not inherited alphabet inputs.

Candidate01 code/model identity is shared; this audit does not prove a future feature adapter's
byte equivalence. Before deployment, identical-frame Python/Android fixtures must cover both hands,
absent/partial hands/body, ROI failures, rotation, timestamps/gaps and padding. Native high-resolution
RGB versus actual phone analysis resolution/framing is a separate observation-quality gap.

## 5. Sequence-recognition fit — RECOMMENDED architecture, not built

Choose **mask-aware causal temporal convolutions → per-time-step character logits → CTC**, with
A–Z + SPACE + CTC blank (proposed 28 output symbols), and a host greedy decoder initially. CTC loss
stays offline; the TFLite graph exports encoder/logits only. Prefer built-in convolution/dense/activation
operations and CPU/XNNPACK; actual export/operator/quantization/parity and device gates remain open.
No ByT5/Transformer/language model, architecture sweep, layer count or tensor/window choice is selected.

CTC learns alignments from clip transcripts without letter-boundary labels. It does not solve wrong
transcripts, truncated clips, utterance start/finish, missing visual information, word spacing or
non-letter rejection. Repeated letters require blanks between equal labels; preserve decoder state
across chunks and preserve final strings such as MM. CTC blank is **not OTHER**, an idle detector or
an observation-failure label. [CTC loss](https://www.tensorflow.org/api_docs/python/tf/nn/ctc_loss),
[decoder semantics](https://www.tensorflow.org/api_docs/python/tf/nn/ctc_greedy_decoder).

The prior isolated A–Z + OTHER plan needs reviewed per-letter intervals and event separation; FSboard
does not provide these reliably. CTC is therefore the simpler fit for this corpus and explicit ABC mode.
Use an explicitly bounded utterance with incremental provisional decoding and an explicit finalization
boundary; do not reuse S2 word events or invent timing from text. A later separate sequence dataset
contract/validator is required: the AZ-1 27-class interval validator remains unchanged and cannot be
treated as a sequence-CTC readiness gate. FSboard is positive sequence data, not verified OTHER/word-sign
negative coverage. Safe open-ended rejection is unproven; custom collection is not authorized here.

## 6. Future Android seam and real cadence — VERIFIED source/evidence, PROPOSED integration

`RecognitionActivity.start` asynchronously loads the runtime; `bindPhoneCamera` binds one front
CameraX RGBA analyzer on `cameraExecutor` (single thread), `KEEP_ONLY_LATEST`, requested 15 FPS,
target 480×360. `Candidate01FrameAnalyzer.analyze` runs existing pose/refiners, constructs
`PhoneRawObservation`, then directly calls `session.consume(observation)` at line 91.
That is the future read-only **observation → exclusive consumer** seam; it is not currently a
pluggable subscription API. Its future wiring would require separate authorization without changing
inference/preprocessing. No second camera, Candidate01 run, landmark stack or diagnostic handedness.

`PhoneProductionSession.consume` synchronously commits through `sentence.add(gloss)` at line 62;
hiding UI output cannot prevent word commits. Future coordinator requirements:

1. WORD forwards to the unchanged word session only. FINGERSPELL forwards to its own adapter/session
   only; **never call the word consume path while FINGERSPELL owns output**.
2. Switch only at a settled boundary or explicit cancellation; generation-tag observations/jobs and
   reject stale alphabet completions. Reset session-local chronological indices/temporal state so
   returning WORD starts at sourceIndex 0; the current word session requires consecutive indices.
3. Bounded ordered alphabet inference uses its own asynchronously loaded TFLite interpreter and one
   owner; immutable observation copies, queue/gap accounting and release/close ownership are required.
   Spell commits go to a separate string/spelling buffer with generation/event identity, preserving
   repeated characters; no SentenceBuilder letter writes. No cross-model score comparison or automatic
   Context Assist routing. These mechanisms are recommendations, not implemented router/session/UI.

Existing metadata-only phone evidence:
`artifacts/recognition_upgrade/perception_vnext/recognition_utility_236_01/`
`s2_r2_representative_phone_final_validation_01/cadence_preflight_result.json`, Xiaomi M2101K7AG,
2026-09-23 empty-scene S2-R2 runtime preflight: 316 observations/84 s including warmup; steady
257 observations/58.4 s (~**4.38 delivered observations/s**), median gap **199.962 ms**, p95
**266.6 ms**, max **466.6 ms**; Candidate01 p50/p95 **194.2/242.2 ms**. This is historical
integrated preflight evidence, not a fresh normal-app/ABC-mode benchmark or fingerspelling measurement.
Current `FpsTracker` ticks after `session.consume`; requested camera FPS and reciprocal latency do not
establish delivered cadence. The project ≥15-FPS product requirement remains unmet by this evidence.

At one CTC step per observation, feasibility requires `T >= transcript_length + adjacent_equal_pairs`.
A metadata-only **hypothetical uniform 5-Hz** timeline (`floor(duration*5)+1` steps) fails this lower
bound for 7,610/81/18 retained TRAIN/DEV/TEST clips. This is not a measured phone replay or recognition
result; even passing the bound does not preserve rapid hand motion. Start without temporal stride,
retain native raw, later test actual chronological phone-cadence views, and explicitly measure current
delivered cadence/coverage before deployment. Do not fabricate frames or alter Candidate01 to hide it.

## 7. Storage/computation practicality — VERIFIED measurements and qualified estimates

The alphabet subset's originals alone total **587.3 GB** (~547 GiB), metadata duration **138.22 h**;
full metadata-listed MP4 payload totals 1.317 TB versus the API's 1.452-TB complete release, which also
includes landmark/documentation material. Per-file retrieval enables bounded batches by frozen manifest;
there is no need to obtain the whole corpus or supplied Holistic landmarks. Use source SHA-256 and
official v13 identity, immutable roles, incremental raw caches and receipts.

This desktop CPU extraction took **71.6–81.1 ms/frame averaged per clip**, including decode/assembly,
excluding model initialization; four NPZs occupy 244,424 bytes. These are neither latency percentiles
nor phone numbers. Raw arrays are 715 uncompressed bytes/frame, including the diagnostic handedness
field. At a hypothetical 30 Hz, the subset would contain ~14.9M frames/~10.7GB raw arrays and require
roughly 14 days on one ~80-ms/frame stream. Native FPS, compression, machine/decoder cost and safe
parallelism change these estimates; no full extraction or throughput guarantee is claimed.

## 8. Unresolved blockers / limits

- Training admission: verify source reflection at sufficient session/release scope; three diagnostic
  clips lack direct evidence. Keep the failed/uncertain sources inventoried rather than force admission.
- Perception: poor e96d hand support, incomplete body evidence, possible overlapping L/R proposals,
  complete J/Z/repeat motion and transcript/clip quality need bounded TRAIN/DEV review. Four clips
  cannot estimate corpus-wide usable yield or cross-signer performance.
- Governance: maintain official roles, version/hash lineage and copied-source checks; source IDs are
  governed pseudonyms, not proof of independence from historical AppHear word signers. Resolve any
  cross-project overlap through permitted custodian/metadata attestations, **never face reidentification**.
  Existing word protected sources remain unopened and cannot supply convenient negatives.
- Evaluation: decide the DEV/TEST phrase overlap policy before model selection. TEST RGB remains sealed;
  its metadata-only statistics are not an evaluation or permission for developer payload review.
- Train/serve: common fields are confirmed, but new feature parity, resolution/framing behavior, delivered
  phone cadence and CTC length feasibility remain deployment gates. No shadow/explicit ABC mode exists.
- Negative/rejection coverage and new sequence governance/validator are missing. The real AZ-1 collection
  package still has zero humans/sessions/samples; its intake pass is not FSboard admission/AZ-2 readiness.

## 9. ChicagoFSWild comparison boundary

No new ChicagoFSWild assessment/download was needed: FSboard has no RGB-access/license-format blocker,
and its signer-disjoint subset is substantial. Switching corpora would not establish AppHear's missing
phone cadence, reflection/feature parity or rejection behavior. The bounded AZ-1 inventory remains the
reference for ChicagoFSWild's supplementary role and access restrictions; no second dataset search began.

## 10. Verification and final decision

Source/core models unchanged; protected 883-file snapshot has zero mismatches. Existing 35 AZ/raw tests
pass. Four TRAIN source/NPZ/receipt hashes and raw invariants validate; evidence indexes and audit-script
snapshots are retained under `datasets/fingerspelling/fsboard_gate_20261002/evidence/`. No model training,
feature export, router/session implementation, custom collection or Android/Context Assist/release change.

**Choose FSboard RGB as the primary candidate corpus and causal temporal convolution + character CTC
with host decoding as the single recommended training/deployment direction.** Its source-to-raw conversion
is demonstrated. Dataset admission and fluent on-device recognition remain unproven and gated by the
specific limits above. Stop at this report; no AZ-2 training or broader experiment is started.

FSBOARD_COMPATIBLE_WITH_LIMITS
