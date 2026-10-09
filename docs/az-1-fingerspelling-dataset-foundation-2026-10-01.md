# AZ-1 — Governed A–Z dataset foundation

2026-10-01. **Result: AZ1_READY_FOR_COLLECTION.** No real letter data, extraction, training or runtime
integration was performed. The dataset is **not ready for AZ-2**.

VERIFIED means Git/source inspection, implemented validator behavior or attributed external publication
evidence. RECOMMENDED means a collection/design choice. UNKNOWN means evidence is still missing.
[AZ-0](az-0-fingerspelling-audit-2026-10-01.md) remains the governing source audit;
[the new operational contract](../context/fingerspelling-dataset-v1.md) specifies this dataset foundation.

## A. Repository state — VERIFIED

- Starting and ending branch: `codex/current-working-text-to-asl-baseline-2026-09-29`.
  HEAD: `cc1f3949114d0ed1dab38d4428191151b37df358`; no branch switch, commit, reset, merge or discard.
- Protected word baseline: `76d93cecd85bf9f76064d320aa4a5791b5f0704a`, reached by
  `baseline/apphear-s2-r2-integration-complete-2026-09-26`, `codex/recognition-stable-ru-d10`, and
  peeled tag `apphear-s2-r2-integration-complete-2026-09-26`.
  The working Text-to-ASL tag `apphear-text-to-asl-working-alphabet-2026-09-29` resolves to current HEAD.
- Pre-existing modifications: `APPHEAR_CONTINUOUS_TRANSITION_AND_READINESS_01_REPORT.md`,
  `context/progress-tracker.md`, `memory.md`. Pre-existing untracked material: `.codex_tmp/`,
  `context/recognition_upgrade/a1_signing_sentinel_01.csv`, AZ-0 report,
  `phone_pull_20260921/`, `phone_pull_s2_exact_parity/`, `phone_pull_s2_r2_independent_validation/`,
  `phone_pull_s2_r2_representative_final_validation/`. These were preserved; handoffs are append-only.
- Context Assist remains separate: clean `feature/conversation-phrase-assist-mvp` worktree at
  `C:/Users/Gigabyte/.codex/worktrees/conversation-phrase-assist/5. Apphear3`, HEAD
  `801fb1d3cda5c31b66e03bd5f40d2b7d619ef3b7`. AZ-0's source-verified UI-placement correction remains
  on that branch; no assistant behavior/schema/flag or branch integration changed here.
- No material starting-state change from AZ-0. Old baseline documentation's earlier assistant HEAD
  remains historical drift already documented in AZ-0; it was not silently rewritten.

## B. Dataset architecture — IMPLEMENTED CONTRACT

Small JSON package: human roster + sessions + original-video samples + reviewed intervals + extraction
references. `apphear.fingerspelling.dataset.v1` fixes A–Z, OTHER ordering, not feature width/time length.
`pipeline/config/fingerspelling_dataset_v1.json` pins Candidate01 assets and explicit collection gates.
The real starter package at `datasets/fingerspelling/az1_collection/package.json` is deliberately empty.

Each sample retains UUID/unique identity, governed human/recorder alias, session/device/date or stable
session key, intended prompt, reviewed transcript/target intervals, split and upstream source role,
raw video path/SHA-256, decoded properties, capture/camera metadata, annotation/quality/use state and
nullable extraction lineage. All repetitions are original recordings; derived windows inherit their
parent and role. Two M occurrences have separate indices; missing perception does not change M to OTHER.
The receipt version is `apphear.fingerspelling.observation_receipt.v1`, wrapping unchanged raw-v1.

No new final alphabet tensor, normalization, temporal window, model architecture or observation math
was selected. Schema details, metadata semantics and label examples are in the operational contract.

## C. Collection protocol — RECOMMENDED, NOT COLLECTED

Start with ten reconciled people: 6 TRAIN, 2 DEV, 2 protected TEST, each across two sessions. Three
distinct people is only the logical split minimum; one person per evaluation role cannot characterize
signer variation. Ten is an initial workload/diversity target, not proof of adequacy or an accuracy claim.

Per session: A–Z at comfortable normal/slower/quicker paces (three attempts each), complete J/Z motion,
preparation/hold/release, realistic front-camera placement and ordinary orientation variation. Rotate
recorded prompt order and vary normal conditions between sessions. Collect a bounded 12-sequence card
including LL/MM/EE, AM/MA/MN/NM/IJ/AZ and three short names/words, plus about ten negative attempts.
Proposed total before review: about 2,000 recordings (1,560 isolated, 240 sequences, 200 negatives).

The first data gate requires all letters from all roster humans, ≥4 reviewed independent isolated clips
per letter/person across ≥2 sessions, reviewed moving J/Z, bounded repeated/transition/short-word
coverage and reviewed OTHER categories. Thresholds are in policy, not an accuracy target. Human review
retains partial/aborted/occluded cases and uncertainty; transitions are not automatically OTHER. Shared
diagnostic prompts are allowed across roles, while short-name TEST prompts are reserved before modeling.
Later TRAIN-diversity learning curves and DEV errors determine expansion; TEST does not drive collection
tuning. A likely final useful dataset may need substantially more people/conditions; its size is UNKNOWN.

## D. Recorder decision — VERIFIED SOURCE / RECOMMENDED REUSE

Reuse `asl recorder/ASLRecorder2/` for the initial isolated capture; **no recorder Java or main app was
changed**. Custom-label support already exists in `data/LabelsRepository.java:addCustomSign`.
Use namespaced labels such as AZ_M / AZ_I / AZ_SEQ_LL, preserving null word gloss; this avoids built-in
word/pronoun I ambiguity. `SessionSetupActivity`/`model/SessionConfig.java` provide repeat counts and
conditions; `data/MetadataManager.java` records sessions and device-scoped signer aliases;
`model/SampleData.java` retains attempts/video references and Stage-E metadata. Governed AZ human ID,
rights, split, hashes and linguistic annotations belong in the external package, not word ingest.
AZ sessions group physical visits; recorder label/configuration batches retain their source IDs and map
to that visit. Their differing IDs do not count as distinct capture visits or additional people.

Material limitations: `recording/RecordingStateMachine.java` fixes capture to **3,000 ms**.
`RecordingActivity.bindCamera` can fall back to preview+analysis without VideoCapture; `saveSample`
can still save an accepted sidecar; `onVideoEvent` discards failed MP4 while leaving metadata. Nominal
30 fps and analysis dimensions are not decoded video facts. These prevent treating recorder acceptance
as a usable sample. Mandatory first smoke: inspect finalized saved MP4 and full J/Z boundaries.

Three seconds may suffice for isolated letters; it is not a guaranteed sequence budget. For longer
sequence/slow-letter/negative attempts, use the phone's existing front-camera video app, explicit prompt
cards and the **same** session/package metadata. Keep saved-video mirroring OFF and original clips.
This is the smallest safe collection fallback, with no new vision stack. A later recorder extension,
if the pilot justifies it, should only add configurable/manual-stop duration and report success after
video finalization. Automatic prompt queues/device metadata can be convenience additions; they are
not prerequisites for this governed collection. No main AppHear recognition changes are necessary.

## E. Data-source inventory — VERIFIED LIMITS / BOUNDED EXTERNAL CHECK

Local findings remain AZ-0's bounded inventory: **0 verified real A–Z positives, 0 verified letter
sequences, 0 verified Candidate01 A–Z artifacts**. The 26 letter GLBs are one avatar's playback assets.
ASL Citizen's 83,399 rows are word data, including lexical ALPHABET/FINGERSPELL/FINGERSPELLING, not
letter supervision. E:/local, samples, Samples2, relocated I: copies, new2 and recorder archives contain
word/background metadata with overlapping device IDs; I-labelled word clips are not letter-I proof.
SEM-LEX's staged 2,425 TRAIN rows/32 IDs/65 word classes are not an alphabet manifest. Large unindexed
archives remain UNKNOWN and unopened. No local source is admitted into the AZ starter package.

Potential future OTHER contributors: rights-cleared, linguistically reviewed, deduplicated **authorized
TRAIN** word/background sources only, after human identity reconciliation. Current policy conservatively
denies historical word roots; a bounded policy revision would be required. Existing protected word/phone
material and evaluation-only VAL cannot contribute. No reuse eligibility or production rights were inferred.

External checks used primary dataset pages/papers, not a large download. None is locally available or
admitted; publication facts below do not prove AppHear extraction quality.

| Candidate | Verified publication/format facts | A–Z / motion / governance / role decision |
|---|---|---|
| [ChicagoFSWild / ChicagoFSWild+](https://home.ttic.edu/~klivescu/ChicagoFSWild.htm) | 7,304 sequences/160 signers; 55,232/260. ASL strings, source URL/start time, frame dimensions/count, processed labels, signer and partition metadata; distributed temporal JPEG frame sequences | Transcript supervision, not reviewed per-letter intervals. Temporal movement/repetitions can be retained; actual J/Z/repeat counts UNKNOWN until permitted inventory. Candidate01 could process original full-frame sequences if timing/crop provenance is sufficient; availability of original MP4 is unverified. Signer IDs enable disjoint auditing; cross-release identity/partition overlap must be checked before combining. Public research release statement does not establish an explicit commercial redistribution license. Supplement only after rights and metadata review |
| [FSboard](https://arxiv.org/pdf/2407.15806) | Paper describes ~151K sequences/147 consenting Deaf signers, Pixel 4A selfie videos, 266 hours; signer/phrase-disjoint splits 117/15/15; release stated CC BY 4.0 | Phone-domain temporal phrase transcripts are promising supplementary data; no per-letter boundary guarantee. J/Z/repeated-letter coverage must be counted/reviewed, not inferred as complete. Original-video processing is feasible in principle; current download endpoint/payload availability and Candidate01 coverage were not verified. Faces/publication-use expectations accompany the release. Preserve official roles, reconcile any identity overlap and re-extract from actual video before admission |
| [Google/Kaggle ASL fingerspelling release](https://www.kaggle.com/competitions/asl-fingerspelling/overview/) | Data card: over 100 Deaf signers, phrase/address/URL/number transcripts, temporal MediaPipe 0.9.0.1 landmarks, noisy automatic clip boundaries; CC-BY stated, with [competition rules](https://www.kaggle.com/competitions/asl-fingerspelling/rules) also governing use | It shares FSboard collection lineage; do not count both as independent data. Landmark-only competition artifacts cannot be re-extracted by Candidate01. Original RGB access and a suitable signer-role manifest are not verified here. Outside-A–Z tokens and ambiguous boundaries need explicit review, not automatic OTHER conversion. Not compatible as direct AZ raw-v1 input; conceptual/annotation reference only until originals/provenance are verified |

Static alphabet image corpora are not selected: no governed local source was verified and images cannot
establish J/Z trajectories, inter-letter movement or repeated-letter behavior. No dataset claims complete
AppHear-compatible A–Z coverage merely because its title says “alphabet” or “fingerspelling”.

## F. Split governance — IMPLEMENTED CHECKS / HUMAN REVIEW REQUIRED

One real human → one AZ role for every device/session/source/window/augmentation. Canonical person keys
and source-namespaced aliases prevent device IDs from becoming extra humans. Exact file copies, duplicate
sample/person/alias/session identities and sample/roster role mismatches fail validation. Hashes do not
detect transcoded copies or undeclared aliases; a frozen human near-duplicate/identity review is required.

Preserve all historical word roles. Protected word TEST, evaluation-only VAL, pristine/replay and reserved
phone-validation identities/material are excluded. Known development-exposed humans cannot become
unseen AZ DEV/TEST. Resolve upstream perception exposure before end-to-end unseen-signer claims.
Unknown historical identity/rights/exposure blocks readiness. No protected video or observation was opened.
TEST metadata is checked; its payload verification requires an authorized custodian's hash-linked report.

## G. Candidate01 extraction — DESIGNED ONLY

Use originals → unchanged pinned `Candidate01Offline` current-frame preprocessing/models → full-source
chronological raw-v1 via the existing `recognition_schema.py` writer → separate versioned receipt.
Reuse `offline_candidate01.py:iter_video_frames/process_rgb/extract_video` with a later alphabet caller;
do not use the legacy 258 extractor, word ingest, S2 `[378]` or Recognition V2 `[96,350]` as AZ features.
The observation common to future runtime is `PhoneRawObservation` before `PhoneProductionSession.consume`;
the future alphabet path must not run Candidate01 again. No caller/extraction or app seam was added here.

Receipt pins model hashes, four preprocessing-source hashes/revision, extraction/decoder versions,
upright unmirrored RGB semantics, video/raw hashes, source time/index range and masks. Python raw retains
diagnostic handedness and NaN missingness; Android normal observation drops handedness and uses masked
zero placeholders. Neither common observation provides useful Z/world input. Video PTS/fps fallbacks
differ from CameraX monotonic timestamps; preserve provenance and examine cadence rather than masking it.
Exact-frame raw parity and source-linked phone-cadence/coverage review remain gates before AZ-2.

## H. Validation tooling — VERIFIED

`pipeline/fingerspelling/validate.py` is an explicitly invoked offline consumer. It checks schema/order,
identity/session/roles, approved source roots and hashes, duplicate files/IDs/humans, protected-source
exclusion before payload read, targets/transcript occurrences/quality, annotation review, Candidate01
raw shapes/schema/chronology/boolean masks/current-frame support rules, receipt/hash/model/source lineage,
J/Z and per-class/human/session/sequence/OTHER coverage. It checks manifest/policy-bound reviewer evidence;
it does not assign labels/splits, decode videos, extract observations, train or import Android.

- **32 synthetic governance tests + 3 existing raw-schema tests: 35 passed.** Tests include M remaining M
  under perception failure, repeated-letter occurrences, corrupt hashes/lineage/masks, leakage/copies,
  quarantine retention/exclusion, report overwrite prevention, protected-source rejection, and a guard
  proving TEST video/raw/receipt payloads are never opened.
- Ruff lint and formatting pass; scoped mypy passes (2 module files, imported historical modules skipped).
  Black confirmed files unchanged outside the sandbox. `/recover` isolated a sandbox temporary-file
  failure while importing its compiled module; no dependency, environment installation or runtime repair.
- [Final real-package validation](../datasets/fingerspelling/az1_collection/evidence/final-validation-2026-10-01.json):
  0 samples, 0 humans, 0 sessions; **0 structural errors, 47 AZ-2 blockers**.
  Intake passes; `--stage az2` returns **2** as expected. Synthetic tests are not training data.
- Manifest/policy edits invalidate approval evidence. The report option requires a new output file;
  it cannot overwrite existing manifests/evidence. There is no automatic protected-test payload read.

Limits: linguistic truth, playable/full videos, rights, undeclared human overlap, transcoded duplicates,
test-payload integrity and end-to-end parity/cadence require accountable reviewer/custodian evidence.
APPROVED metadata is an attestation, not cryptographic identity authentication. These limits are explicit
gates, not claimed automation. No accuracy metric follows from the test count.

## I. Missing data and remaining decisions

All real participant/consent/identity/session/source data is missing. Required next evidence: reviewed
A–Z per-human/class/role coverage; full moving J/Z; repeated letters, transitions and short words;
representative linguistic OTHER; original-video hashes and decoded properties; Candidate01 raw receipts;
source-linked quality/mask/cadence review; near-duplicate review; sealed TEST custodian integrity evidence.
Recorder device feasibility, approved external payload access/rights, definitive external per-letter
coverage and suitable final alphabet representation are UNKNOWN. Custom phone-domain collection remains
required by the verified local inventory; no architecture/window choice is justified yet.

## J. AZ-2 decision and protected boundary

**AZ1_READY_FOR_COLLECTION.** Contract, bounded protocol, recorder fallback, identity/split governance
and validation tooling exist and are tested. No collection has begun and no actual dataset passes the
gates. **NO-GO for AZ-2 training** until real data satisfies the governed checks and human evidence.
Next action: reconcile/enroll TRAIN participants, freeze roles/consent, run saved-video capture smoke.

Protected and untouched: all Android/recorder source and assets; Candidate01/raw-v1/math/models;
S2-R2/378/normalization; PRE_OR_POST recovery/Admission/CONFIG01/lifecycle/re-arm; materializer;
Recognition V2/masks/frozen 236 recognizer/vocabulary; PhoneProductionSession and SentenceBuilder;
Sign-to-Text/Hear/TTS; Context Assist provider/prompts/schema/matcher/flags/corrected UI; existing dataset
roles and Git baselines. No AlphabetSession, SpellingBuffer, mode hint/router, model training or release
activation was implemented. Future commit ownership must isolate the internally committing word session,
preserve repeated letters separately, and remain explicit-mode/shadow-governed as AZ-0 recommends.

Final integrity check: 883 pre-existing tracked Android/recorder/model/deploy/perception files are
byte-identical to the starting snapshot. AZ-0 and the unrelated readiness report are byte-identical;
previous memory/progress/feature-schema bytes are preserved before append-only AZ handoffs/registry.
No runtime build/device evaluation was warranted by this offline-only milestone.

## Review result

`/review`: plan alignment PASS; system-integrity PASS; collection-foundation gate PASS.
Critical/important/minor implementation findings: 0/0/0. AZ-2 data gate FAIL, as expected from the empty
package and 47 documented blockers; this is required pending collection evidence, not a training approval.
`/imprint` registered only the new offline dataset/receipt/validator contract. No F/S4 parity surface was
changed; future raw/cadence review and final alphabet feature parity remain explicit gates. Recommendation:
use the foundation for staged collection and stop before extraction/training/runtime work.

`AZ1_READY_FOR_COLLECTION`
