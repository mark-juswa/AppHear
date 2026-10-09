# AZ-1 fingerspelling dataset contract

2026-10-01. Offline collection/governance only. Governing source findings:
[AZ-0](../docs/az-0-fingerspelling-audit-2026-10-01.md).
This contract does not change any word feature schema, model or Android behavior.
The user-authorized AZ-1 is a separate data-foundation milestone, outside the old word build queue.

## Architecture and terminology

- **Person:** one human represented by a governed pseudonymous `person_key`; device IDs are aliases.
- **Sample:** one original recording, not a derived window, copy, augmentation or signer.
- **Intended:** the prompt. **Verified transcript:** what linguistic video review confirms was performed.
- **Model target:** A–Z or OTHER on a reviewed interval. **Quality:** observation/capture condition,
  independent of the target. OTHER is neither CTC blank nor an end-of-word command.
- **Ready:** real data plus reviewed identity, rights, coverage, lineage and sealed-test evidence;
  passing tooling alone means only ready for collection.

Build order: frozen state/AZ-0 → contract and capture plan → validator/synthetic tests → collection →
human review → authorized Candidate01 raw extraction → data gate. No training is part of AZ-1.
No runtime flag is required for this explicitly invoked offline validator: it has no app import or
shipping path. Future model input width, temporal length, encoder and normalization remain open.

## Package and identity records

Schema: `apphear.fingerspelling.dataset.v1`. Class order is exactly A through Z, then OTHER
(indices 0–26); reject reordered lists. Policy and initial coverage gates live in
`pipeline/config/fingerspelling_dataset_v1.json`. Start from
`datasets/fingerspelling/az1_collection/package.json`, currently **empty**.

Layout: `package.json`; immutable `raw/` videos; rebuildable `observations/` NPZ plus receipts;
`evidence/` review reports and approvals; optional `private/` identity/consent ledger kept outside Git.
The package's local ignore file excludes raw/observations/private. Do not commit identifying consent
records or publicize protected payloads. The pseudonymous roster and review metadata are sufficient
for normal development. Raw files can reside on a named external collection disk instead.

| Record | Required fields / meaning |
|---|---|
| Package | `schema_version`, unique `dataset_id`, explicit `fixture` boolean, exact `class_order`, `source_roots`, `signers`, `sessions`, `samples`, `approvals_path` |
| Source root | `path`, `source_id`, `origin_role` (`NEW_AZ_CAPTURE` or approved `EXTERNAL_TRAIN`), `review_state=APPROVED`, `rights_ref`; relative paths resolve against package directory, absolute paths permitted; exactly one root may cover a source |
| Human roster | `signer_id` (e.g. AZ-P001), unique `person_key`, `split_role`, nonempty source-namespaced `aliases` (e.g. recorder:deviceA:S001), `identity_review=RESOLVED`, `identity_evidence_ref`, `rights=APPROVED`, `consent_or_license_ref`, `historical_role_review=CLEARED`, `word_role`, `perception_exposure` |
| Session | unique `session_id`, `signer_id`, `device_id`, stable `session_key`, optional `recording_date`; `capture_conditions` and `camera` objects with unknown fields explicitly null |
| Sample | unique `sample_id` (UUID preferred), `signer_id`, `source_signer_alias`, `session_id`, `split_role`, `kind` (ISOLATED/SEQUENCE/NEGATIVE), `intended`, stable `prompt_id`, positive `attempt_index`, `training_use` (INCLUDE/QUARANTINE), `source`, `annotation`, nullable `extraction`; sequences also carry `sequence_purpose` (repeated/transition/spelled_word) |
| Source | `path`, SHA-256 `sha256`, `source_id`, `origin_role`, decoded `duration_ms`; before data readiness also `original_video=true`, measured `native_fps`, `width`, `height`; preserve recorder sidecar separately with its hash/reference when available |
| Annotation | `state` (PENDING/REVIEWED/QUARANTINED), nullable `verified_transcript`, nonempty `observation_quality` list, `segments`; REVIEWED additionally requires distinct `annotator_id`/`reviewer_id`, `video_reviewed=true` |
| Segment | half-open source-time `[start_ms,end_ms)`, `model_target`, nonnegative `boundary_uncertainty_ms`; letters require occurrence `letter_index` into verified transcript; J/Z require `motion_confirmed=true`; OTHER has null `letter_index`, optional diagnostic `other_subtype` required for this pilot's coverage reporting, and a human `non_letter_reason` |
| Extraction | `raw:{path,sha256}`, `receipt:{path,sha256}`; null before extraction is legal intake but blocks AZ-2 |

Camera metadata: lens/front-back, manufacturer/model or anonymized device identity, camera ID if known,
saved-video mirroring, rotation, resolution and measured fps. Capture conditions: date/session, natural
speed category, distance, seated/standing, lighting, background, dominant hand, orientation variation,
operator notes. Missing optional descriptive values are null, never fabricated. For this phone-domain
pilot, readiness requires front lens and `saved_video_mirrored=false`; unknown semantics block readiness.
Inspect the **saved original**, since mirrored preview says nothing about stored video chirality.
An AZ session means a physical capture visit, not one recorder label/configuration batch. Map all
recorder `session_id` batches from that visit to one governed AZ session; retain their original IDs
in sidecar provenance. Per-attempt speed/conditions can be retained in an optional sample
`capture_conditions` object when different from the session defaults. Two prompt batches in one visit
must not manufacture two-session coverage.

One source recording is one sample. Do not register subclips or windows as new independent recordings.
Use its ordered segments instead. Later derived records must inherit `sample_id`, human and split,
plus parent artifact hash and view/augmentation recipe; they add zero humans/source recordings.
Keep original sidecar IDs and declared `video_file` mapping; do not guess adjacent filenames.

## Label policy

`intended=M`, `verified_transcript=M`, target M, quality `[occluded]` is valid. The same applies to
`perception_failure`: a genuine letter never becomes OTHER because a mask or presence score failed.
All quality states persist even when a clip is quarantined. Capture quality and Candidate01 validity
are different facts; valid crops are not a physical-visibility annotation.
Explicit QUARANTINE attempts remain in the source inventory but add no coverage and need no extraction.
They do not individually block readiness; pending INCLUDED attempts do. INCLUDED genuine-letter samples
with zero observed hands block use pending review/quarantine and replacement coverage, while retaining
their genuine target. The validator reports observed-hand/body frame counts and timestamp gaps;
nonzero coverage alone does not prove sufficient letter evidence and still needs extraction review.

The target follows video review, not the prompt. A prompted M that was actually N can be reviewed as
transcript/target N with an explanation. A truly unresolvable attempt remains PENDING/QUARANTINED;
do not manufacture an OTHER label. A genuine incomplete letter may remain a positive/partial sample
or be quarantined; only a confirmed non-letter aborted movement can become OTHER/partial_attempt.

OTHER retains one model class and diagnostic subtypes: idle, word_sign, transition, non_letter_gesture,
partial_attempt, occlusion, perception_failure, difficult_letter_like_negative. The last two quality-like
names never authorize converting letter evidence to OTHER. For example, a failed observation during a
confirmed idle interval can carry OTHER/perception_failure; failed perception of M remains M.

Transitions are reviewed individually. An interval still expressing either letter is letter evidence;
only confirmed non-letter intervals get OTHER/transition. Uncertain/coarticulated boundaries stay
quarantined or explicitly uncertain until adjudicated. No frame-wide transition auto-label exists.
Gaps between annotated segments are **unlabelled**, not automatic OTHER.

Verified transcripts contain A–Z only; an actual non-letter clip uses the empty string. MM has two
ordered M segments with indices 0 and 1, even if their handshapes look similar. Do not collapse equal
letters, concatenate isolated videos to invent natural sequences, or add spaces/digits as new targets.
Retain start/hold/release context in the original and raw package. A letter segment covers its reviewed
production, including motion for J/Z; these are annotation bounds, not a fixed model window.

## Collection protocol and initial scale

Minimum logical split feasibility is three distinct humans, one per role. This is insufficient evidence
of generalization. The **initial engineering target** is 10 humans: 6 TRAIN / 2 DEV / 2 PROTECTED_TEST,
with two genuinely different capture sessions per person. Recruit ASL fingerspellers with meaningful
variation in dominant hand, signing experience, hand appearance and natural style. Do not substitute
many repetitions from one person for recruitment. Recruit new people when historical identity or
protected evaluation exposure is unresolved.

1. Pilot recorder/file integrity with consenting TRAIN signers first. Verify saved front-camera MP4,
   actual duration/fps/orientation and full J/Z motion. This is a capture feasibility check, not accuracy.
2. In each session collect all 26 isolated letters, three attempts each: comfortable natural pace,
   slower comfortable pace, quicker comfortable pace. Rotate prompt order using a recorded prompt
   card/order; do not always rehearse alphabetical order. Give rest breaks. Retain natural preparation,
   full production/hold and release; never rush J/Z to fit a timer.
3. Use realistic phone placement showing head/upper torso and the complete signing hand. Vary normal
   angle/distance/lighting between sessions without prescribing extreme distortions. Save originals;
   no destructive trimming, interpolation, mirroring or recorder-feature acceptance gate.
4. Per session add a bounded 12-sequence card: LL, MM, EE, AM, MA, MN, NM, IJ, AZ, and three short
   spelled words/names. Let repeated letters use natural repeat movement; also collect a semi-separated
   version across sessions. Suggested short-word prompts: TRAIN ANNA/EMMA/JAZZ; DEV ELLEN/MAYA/JUNE;
   TEST JILL/ZOE/LIZA. Freeze evaluation name lists before modeling; no test-video developer review.
   Common diagnostic transitions/repetitions may occur across roles; human disjointness is still strict.
5. Per session collect about ten negative attempts across idle/ordinary rest, freshly recorded word
   signs, non-letter gestures, confirmed non-letter aborted attempts and difficult letter-like negatives.
   Do not intentionally remove completed letters from aborted clips. Retain occluded/blurred/failed
   attempts separately, without changing semantic targets. An ASL reviewer adjudicates ambiguous
   letter-like negatives; diagnostic subtype tags do not establish linguistic correctness.
6. Two-pass linguistic/content/boundary review; preserve disagreements and original prompts. Retake
   missing coverage, never erase the failed attempt. Preserve condition and quality distributions.

Acquisition target: roughly **1,560 isolated clips + 240 sequence clips + 200 negative clips** before
review, across 20 sessions. This is workload budgeting, not a statistically established sample minimum.
The configurable first-experiment floor is 4 reviewed independent isolated clips per letter/person,
distributed across 2 sessions, at least 7 reviewed sequence clips/person including a short spelled
word/name, LL/MM/EE and AM/IJ/AZ coverage in every role. OTHER requires idle, word_sign,
non_letter_gesture, partial_attempt and difficult_letter_like_negative in each role, from at least
2 TRAIN humans and 1 DEV/TEST human per subtype. Every reviewed J/Z target requires full-motion review.
There is no requirement to fabricate perception failures or non-letter transition labels to fill a quota.
These gates do not promise performance. After AZ-2 is separately authorized, TRAIN-signer learning
curves and DEV per-signer/class/sequence errors decide expansion. Protected TEST never drives tuning.

## Split governance and protected access

Assign people before extraction, preprocessing or fitting. Freeze roster/version and collection roles.
All sessions, clips, raw sequences, windows and augmentations of a human inherit one AZ role. A new
device alias maps to the existing person; it never creates another signer. Preserve a private human
identity reconciliation ledger and reviewer reference. A duplicate `person_key`, alias or exact source
hash is an error. Device/session duplicate keys cannot manufacture extra sessions. Human near-duplicate
review must also address transcoded/copied sources, near-identical takes and alias collisions the hash
validator cannot discover. Copies on E:/I: and archives do not count again.

`word_role`: NONE = reviewed absence of known project word exposure; TRAIN/DEV = development-exposed
human, permitted only in AZ TRAIN for **new** AZ capture; PROTECTED = any protected word TEST,
evaluation-only VAL, pristine/replay or reserved phone-validation human, excluded from this pilot.
Do not infer NONE from a new device ID. Historical uncertainty is quarantined. Existing source roles
remain immutable; no word protected/VAL/phone video becomes OTHER. The starter validator conservatively
denies historical word roots and protected path markers entirely. A future authorized TRAIN-only reuse
needs a bounded provenance/identity/rights review and explicit policy revision, not renaming a path.

For AZ DEV/TEST, `perception_exposure=UNEXPOSED` means no known AppHear Candidate01/perception development
or training participation after reconciliation; unknown exposure blocks an unseen-human claim. General
third-party pretrained model populations remain an acknowledged uncertainty, not a claimed global proof.

TRAIN fits representations/model parameters; DEV selects/calibrates/boundary policies; PROTECTED_TEST
is sealed final evaluation. This tool reads only TEST manifest metadata, not TEST video, NPZ or extraction
receipt payload. An authorized custodian must verify those payloads separately and provide a frozen,
hash-linked metadata integrity report. No test payload access is authorized by running this validator.
No automatic splitting, identity inference or protected payload discovery is implemented.

## Candidate01 extraction design — not executed in AZ-1

Original source MP4/hash → pinned `Candidate01Offline.process_rgb` on chronological full-source frames
using `iter_video_frames(video,None)` → unchanged raw-v1 NPZ via `save_raw_sequence` → separate alphabet
extraction receipt → validated package. Reuse `pipeline/perception_vnext/offline_candidate01.py`,
`hand_roi.py`, `hand_refiner.py`, `recognition_schema.py`; do not edit them. A later thin alphabet caller
must validate authorized source/identity/roles first and use only TRAIN/DEV unless protected access is
separately authorized. No old `pipeline.ingest`, Stage-E/258 extractor, S2 features or V2 conversion.

`extract_video` is reusable for isolated samples through a row adapter (`raw_video_path/hash`,
`sample_id`, `signer_group_id`, `split`, `source_dataset`, `class_id`, `canonical_gloss`, empty span).
Its word-named label fields are diagnostic metadata only in AZ: add an explicit AZ label namespace;
use class index for isolated reviewed targets, -1 for unresolved/sequence content, and keep supervision
in the sample's segments. For sequences use the same frame functions/full-source assembly or override
the word-oriented `duration_scope` metadata to `whole_source_video` in the new wrapper. Do not run any
word feature builder or infer a single word label for a multi-letter source. This adapter is **designed,
not implemented**; no videos were extracted in AZ-1.

Pinned models are the two SHA-256 identities in the policy (DWPose-t ONNX and 224 hand refiner). Verify
actual files against these pins before constructing the extractor. The receipt stores:

- `schema_version=apphear.fingerspelling.observation_receipt.v1`, raw schema, sample/human/split;
- `candidate_id`, `candidate01_assets` map, `source_sha256`, `raw_sha256`, `whole_source_video=true`;
- `extraction_version`, Git `code_revision`, `preprocessing_source_sha256` for the four source modules;
- `image_semantics=UPRIGHT_UNMIRRORED_SOURCE_RGB`, `decoder_version` (OpenCV/backend version),
  `timestamp_policy`, measured source-video properties/rotation, `frame_count`, `timestamp_range_ms`.

Preprocessing is unchanged: RGB uint8, upright rotation/no analysis mirror; DWPose NCHW 256×192,
existing source transform/bilinear zero-border/mean/std; current-frame anatomical proposal ROI;
refiner NHWC 224×224 RGB/255; exact current acceptance/mask rules. The source hashes pin the arithmetic,
not a newly reimplemented preprocessor. Preserve actual indices/timestamps and timestamp provenance:
container POS_MSEC, frame-index/container-fps fallback or monotonic-fps repair. These are decoded video
timestamps, not Android monotonic CameraX clock values. Record fallback use; variable-frame-rate/timing
uncertainty needs review rather than being hidden as uniformly sampled truth.

Raw retains `[T,2,21,2]` hand XY, `[T,2,21]` joint masks/proposal supports, `[T,2]` presence/observed/proposal
states, `[T,2,3]` ROIs, eight body XY/support/masks/availability, source size/index/timestamp and metadata.
T is native variable length; no resampling, final feature width or model window is chosen. Python raw
also has `[T,2] hand_handedness_diagnostic`; Android's normal `PhoneRawObservation` drops it. Missing
Python geometry/presence may be NaN with false masks; Android uses zero placeholders with false masks.
Z/world data are not available in the common contract. Preserve diagnostics but exclude Python-only
handedness, Z/world and implicit visibility from any future serving input. Pin this difference explicitly.

Before AZ-2, review a small authorized TRAIN/DEV extraction sample against source video for decoded
orientation, complete motion, coverage, timestamps/gaps and mask correctness; retain exact-frame
Python/Android raw parity evidence using the existing Candidate01 path. Native high-fps video does
not prove phone analyzer cadence suffices: retain native raw and evaluate chronological actual-frame
cadence views on TRAIN/DEV, without copied/interpolated observations or retuning Candidate01/S2.
Final alphabet feature parity belongs to the later separately versioned representation milestone.

## Validation and evidence gates

Run `.venv/Scripts/python.exe -m pipeline.fingerspelling.validate <package.json>` for intake; append
`--stage az2 --report <new-report.json>` to check data readiness. Exit 0 means the selected stage passed;
exit 2 means it failed. Intake allows pending annotations/extraction but reports blockers. Empty intake
may pass; it cannot establish readiness. Validation only hashes/reads specifically registered development
files. It does not decode videos, run models, discover extra datasets, fit features or rewrite manifests.

`approvals_path` points to a separate JSON under `evidence/` so approval hashes do not form a manifest
self-hash cycle. Each approval is keyed by policy name and carries `state=APPROVED`, `reviewer_id`,
exact frozen `package_sha256`, `policy_sha256`, and `evidence:{path,sha256}` under `evidence/`.
Required approvals: identity_and_rights, near_duplicate_review, candidate01_extraction_review,
phone_cadence_and_raw_parity, protected_test_integrity. Any package/policy edit invalidates approval.
Evidence documents must contain the reviewed population, procedure, findings and unresolved gaps;
protected-test evidence is metadata only. Approvals are accountable human attestations, not digital
signature verification or proof of unseen identities. Do not treat arbitrary APPROVED strings as a
substitute for these reviews. The validator reports data gates; it never authorizes training itself.

Checks cover schema/order, identity/session/role, sources/hashes, exact copies, protected sources before
read, targets/quality/repeated occurrences, whole-source raw-v1 shape/schema/timing/masks and pinned
receipt lineage, J/Z, per-human/class/session coverage, bounded sequences/OTHER, frozen review evidence.
Limits: no automatic human matching, near-duplicate video search, linguistic/capture correctness,
license judgment, decoding proof, cryptographic reviewer authentication or reading of TEST payloads.
These require the specified human/custodian evidence; failures remain explicit blockers.

Next action: enroll and reconcile the initial TRAIN participants, freeze their AZ roles/consent, then
perform the saved-video recorder smoke. No real samples or approvals are present yet.
